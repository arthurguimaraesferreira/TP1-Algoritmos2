import dash
import dash_leaflet as dl
import dash_leaflet.express as dlx
from dash import html, Output, Input, dash_table, dcc
import pandas as pd
import json
import webbrowser
from threading import Timer

from KDTree import build_kdtree, range_search

def open_browser():
    webbrowser.open_new("http://127.0.0.1:8050/")


def parse_point(wkt):
    # wkt tem o formato "POINT (lon lat)"
    lon, lat = wkt.replace("POINT (", "").replace(")", "").split()
    return [float(lat), float(lon)]


def main():
    # Carregar o GeoJSON real do polígono de Belo Horizonte
    with open('belo_horizonte.geojson', 'r', encoding='utf-8') as f:
        bh_geojson = json.load(f)


    # Ajustar leitura latitude e longitude
    df = pd.read_csv('Bares_e_CDB2025.csv')
    df['coords'] = df['GEOMETRIA'].apply(parse_point)

    # Prepara a lista de pontos para a KDTree
    pts = [(row['coords'], idx) for idx, row in df.iterrows()]

    # Constrói a KDTree a partir dos pontos de coordenadas
    kdtree_root = build_kdtree(pts, depth=0)


    # Criar app
    app = dash.Dash(__name__)

    app.layout = html.Div([
        html.Label("Filtrar participantes do Comida Di Buteco 2025:"),
        dcc.Checklist(
            id="cdb_filter",
            options=[{"label": "Exibir apenas participantes", "value": "cdb"}],
            value=[],
            inline=True,
            inputStyle={"margin-right": "5px"},
            style={"margin-bottom": "10px"}
        ),
        dl.Map(
            id="map",
            center=[-19.9191, -43.9386],
            zoom=12,
            style={'width': '100%', 'height': '500px'},
            children=[
                dl.TileLayer(),
                # polígono de BH
                dl.GeoJSON(data=bh_geojson,
                           style={"color": "blue", "weight": 2, "fillOpacity": 0.1}),
                # máscara para fora de BH
                dl.Polygon(
                    positions=[
                        [[-90, -180], [-90, 180], [90, 180], [90, -180], [-90, -180]],
                        bh_geojson['features'][0]['geometry']['coordinates'][0]
                    ],
                    color="black", fillColor="black", fillOpacity=0.7
                ),
                # Grupo que receberá os marcadores filtrados
                dl.GeoJSON(id="markers-layer", cluster=True, zoomToBoundsOnClick=True, superClusterOptions={"radius": 100}),

                # Ferramenta de desenho: permite desenhar apenas retângulos
                dl.FeatureGroup([
                    dl.EditControl(
                        id="edit_control",
                        draw={
                            "rectangle": True,
                            "polyline": False,
                            "polygon": False,
                            "circle": False,
                            "marker": False,
                            "circlemarker": False
                        },
                        edit={"edit": False, "remove": True} # permite apagar o retângulo desenhado
                    )
                ])
            ]
        ),

        # Tabela para exibir informações dos pontos dentro do retângulo
        dash_table.DataTable(
            id="table",
            columns=[
                {"name": "Nome", "id": "nome"},
                {"name": "Início",           "id": "data_inicio"},
                {"name": "Possui Alvará?",    "id": "alvara"},
                {"name": "Endereço",         "id": "endereco"},
                {"name": "Participante do Comida Di Buteco 2025?", "id": "cdb2025"}
            ],
            data=[],      # será preenchido pelo callback
            style_cell={'textAlign': 'left', 'padding': '4px'},
            style_header={'fontWeight': 'bold'}
        )
    ], style={'width': '80%', 'margin': '0 auto'})

    # Callback que atualiza marcadores quando o usuário dá zoom e move o mapa
    @app.callback(
    Output("markers-layer", "data"),
    Output("table", "data"),
    Input("map", "zoom"),
    Input("map", "bounds"),
    Input("edit_control", "geojson"),
    Input("cdb_filter", "value")
    )
    def update_visible_markers(zoom, bounds, drawn_geojson,cdb_filter):
        if bounds is None:
            raise dash.exceptions.PreventUpdate

        filtered_indices = []

        # Caso existam retângulos desenhados:
        if drawn_geojson and "features" in drawn_geojson and len(drawn_geojson["features"]) > 0:
            for feature in drawn_geojson["features"]:
                if feature["geometry"]["type"] == "Polygon":
                    coords = feature["geometry"]["coordinates"][0]  # retângulo = lista de 5 pontos (1º == último)
                    lats = [pt[1] for pt in coords]
                    lons = [pt[0] for pt in coords]
                    min_lat, max_lat = min(lats), max(lats)
                    min_lon, max_lon = min(lons), max(lons)
                    rect = ((min_lat, min_lon), (max_lat, max_lon))
                    found = []
                    indices = range_search(kdtree_root, rect, found)
                    filtered_indices.extend(indices)

            # Remover duplicatas
            filtered_indices = list(set(filtered_indices))
        else:
            # Se não houver retângulo desenhado, usa os bounds visíveis
            (sw_lat, sw_lon), (ne_lat, ne_lon) = bounds
            rect = ((sw_lat, sw_lon), (ne_lat, ne_lon))
            found = []
            filtered_indices = range_search(kdtree_root, rect, found)

        # Criar marcadores e tabela
        markers = []
        table_data = []
        for idx in filtered_indices:
            row = df.iloc[idx]
            is_cdb = str(row['CDB2025_Participante']).strip().upper() == "SIM"

            if "cdb" in cdb_filter and not is_cdb:
                continue
            lat, lon = row['coords']
            is_cdb = str(row['CDB2025_Participante']).strip().upper() == "SIM"
            nome_exibir = (
                row['NOME_FANTASIA']
                if pd.notna(row['NOME_FANTASIA']) and row['NOME_FANTASIA'].strip()
                else row['NOME']
            )
            popup_text = (
                f"<b>{nome_exibir}</b><br>"
                f"Início: {row['DATA_INICIO_ATIVIDADE']}<br>"
                f"Alvará: {'Sim' if str(row['IND_POSSUI_ALVARA']).upper() in ('1','S','SIM') else 'Não'}<br>"
                f"{row['NOME_LOGRADOURO']}, {row['NUMERO_IMOVEL']} – {row['NOME_BAIRRO']}<br>"
                f"<b>CDB2025 Participante:</b> {'Sim' if is_cdb else 'Não'}"
            )
            if is_cdb:
                prato = row['PRATO'] if pd.notna(row['PRATO']) else ''
                desc = row['DESC_PRATO'] if pd.notna(row['DESC_PRATO']) else ''
                prato = str(prato).strip()
                desc = str(desc).strip()
                if prato:
                    popup_text += f"<br><b>Prato Participante:</b> {prato}"
                if desc:
                    popup_text += f"<br><b>Descrição:</b> {desc}"

            markers.append({
                "lat": lat,
                "lon": lon,
                "popup": popup_text,
                "radius": 6,
                "fillOpacity": 0.8
            })

            table_data.append({
                "nome": nome_exibir,
                "data_inicio": row["DATA_INICIO_ATIVIDADE"],
                "alvara": "Sim" if str(row["IND_POSSUI_ALVARA"]).upper() in ("1", "S", "SIM") else "Não",
                "endereco": f"{row['NOME_LOGRADOURO']}, {row['NUMERO_IMOVEL']} – {row['NOME_BAIRRO']}",
                "cdb2025": "Sim" if is_cdb else "Não"
            })

        return dlx.dicts_to_geojson(markers), table_data

    # Abre o browser e roda
    Timer(1, open_browser).start()
    app.run(debug=False)


if __name__ == '__main__':
    main()