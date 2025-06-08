import dash
import dash_leaflet as dl
from dash import html, Output, Input, dash_table
import pandas as pd
import json
import webbrowser
from threading import Timer

from KDTree import KDNode, build_kdtree, range_search

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
    df = pd.read_csv('Tabela_Bares_e_Restaurantes_e_CDB2025.csv')
    df['coords'] = df['GEOMETRIA'].apply(parse_point)

    # Prepara a lista de pontos para a KDTree
    pts = [(row['coords'], idx) for idx, row in df.iterrows()]

    # Constrói a KDTree a partir dos pontos de coordenadas
    kdtree_root = build_kdtree(pts, depth=0)


    # Criar app
    app = dash.Dash(__name__)

    app.layout = html.Div([
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
                dl.LayerGroup(id="markers-layer"),

                # 4.1) Ferramenta de desenho: permite desenhar apenas retângulos
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

        # 4.2) Tabela para exibir informações dos pontos dentro do retângulo
        dash_table.DataTable(
            id="table",
            columns=[
                {"name": "Nome", "id": "nome"},
                {"name": "Início",           "id": "data_inicio"},
                {"name": "Possui Alvará",    "id": "alvara"},
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
        Output("markers-layer", "children"),
        Output("table", "data"),
        Input("map", "zoom"),
        Input("map", "bounds"),
        Input("edit_control", "geojson")
    )
    def update_on_zoom_or_draw(zoom, bounds, feature_collection):
        # Caso 1: Zoom < 15 → nenhum ponto no mapa e nenhum ponto na tabela
        if not zoom or zoom < 15:
            return [], []

        # Caso 2: Zoom ≥ 15, mas sem retângulo desenhado → filtra pontos a serem plotados por bounds USANDO KD-Tree
        if not feature_collection or not feature_collection.get("features"):
            if not bounds:
                return [], []
            (sw_lat, sw_lon), (ne_lat, ne_lon) = bounds

            # Índices Visíveis = pontos achados na busca pela KD-Tree
            indices_visiveis = range_search(kdtree_root, ((sw_lat, sw_lon), (ne_lat, ne_lon)), found=[])

            # Plotar os markers
            markers = []
            for idx in indices_visiveis:
                row = df.iloc[idx]
                lat, lon = row['coords']
                is_cdb = str(row['CDB2025_Participante']).strip().upper() == "SIM"
                nome_exibir = (
                    row['NOME_FANTASIA']
                    if pd.notna(row['NOME_FANTASIA']) and row['NOME_FANTASIA'].strip()
                    else row['NOME']
                )
                possui_alvara = (
                    'Sim'
                    if str(row['IND_POSSUI_ALVARA']).upper() in ('1','S','SIM')
                    else 'Não'
                )
                endereco = f"{row['NOME_LOGRADOURO']}, {row['NUMERO_IMOVEL']}"
                if pd.notna(row['COMPLEMENTO']) and row['COMPLEMENTO'].strip():
                    endereco += f" – {row['COMPLEMENTO']}"
                endereco += f" – {row['NOME_BAIRRO']}"
                popup_html = (
                    f"{nome_exibir} // "
                    f"Início: {row['DATA_INICIO_ATIVIDADE']} // "
                    f"Alvará: {possui_alvara} // "
                    f"{endereco} // "
                    f"CDB2025 Participante: {'Sim' if is_cdb else 'Não'}"
                )

                markers.append(
                    dl.Marker(
                        position=[lat, lon],
                        children=[
                            dl.Tooltip(nome_exibir),
                            dl.Popup(popup_html)
                        ]
                    )
                )
            return markers, []

        # Caso 3: Zoom ≥ 15 e há retângulo desenhado → filtra pela KD-Tree e poẽ na tabela
        rectangle_feature = feature_collection["features"][0] # Retâgulo desenhado foi esse
        coords = rectangle_feature["geometry"]["coordinates"][0]
        # coords: lista de vértices em [ [lon,lat], ... ]
        lons = [pt[0] for pt in coords]
        lats = [pt[1] for pt in coords]
        sw_lon, ne_lon = min(lons), max(lons)
        sw_lat, ne_lat = min(lats), max(lats)
        rect = ((sw_lat, sw_lon), (ne_lat, ne_lon)) # Retângulo para busca na KD-Tree definido

        # range_search retorna índices de df dentro desse rect
        indices_dentro = range_search(kdtree_root, rect, found=[])

        markers = []
        table_rows = []
        for idx in indices_dentro:
            row = df.iloc[idx]
            lat, lon = row['coords']
            is_cdb = str(row['CDB2025_Participante']).strip().upper() == "SIM"
            nome_exibir = (
                row['NOME_FANTASIA']
                if pd.notna(row['NOME_FANTASIA']) and row['NOME_FANTASIA'].strip()
                else row['NOME']
            )
            possui_alvara = 'Sim' if str(row['IND_POSSUI_ALVARA']).upper() in ('1','S','SIM') else 'Não'
            endereco = f"{row['NOME_LOGRADOURO']}, {row['NUMERO_IMOVEL']}"
            if pd.notna(row['COMPLEMENTO']) and row['COMPLEMENTO'].strip():
                endereco += f" – {row['COMPLEMENTO']}"
            endereco += f" – {row['NOME_BAIRRO']}"
            popup_html = (
                f"{nome_exibir} // "
                f"Início: {row['DATA_INICIO_ATIVIDADE']} // "
                f"Alvará: {possui_alvara} // "
                f"{endereco} // "
                f"CDB2025 Participante: {'Sim' if is_cdb else 'Não'}"
            )

            markers.append(
                dl.Marker(
                    position=[lat, lon],
                    children=[
                        dl.Tooltip(nome_exibir),
                        dl.Popup(popup_html)
                    ]
                )
            )

            # Coloca na tabela
            table_rows.append({
                "nome": nome_exibir,
                "data_inicio": row['DATA_INICIO_ATIVIDADE'],
                "alvara": possui_alvara,
                "endereco": endereco
            })

        return markers, table_rows


    # Abre o browser e roda
    Timer(1, open_browser).start()
    app.run(debug=False)


if __name__ == '__main__':
    main()