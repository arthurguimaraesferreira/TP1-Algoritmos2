import dash
import dash_leaflet as dl
from dash import html, Output, Input
import pandas as pd
import json
import webbrowser
from threading import Timer

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
    df = pd.read_csv('bares_restaurantes_reduzido.csv')
    df['coords'] = df['GEOMETRIA'].apply(parse_point)


    # Criar app
    app = dash.Dash(__name__)

    app.layout = html.Div([
        dl.Map(
            id="map",
            center=[-19.9191, -43.9386], zoom=12, style={'width': '100%', 'height': '500px'},
            children=[
                dl.TileLayer(),  # Camada base (pode ajustar ou remover)
                # Mostrar o polígono real
                dl.GeoJSON(data=bh_geojson, style={"color": "blue", "weight": 2, "fillOpacity": 0.1}),
                # Máscara para áreas fora do polígono real
                dl.Polygon(positions=[
                    [[-90, -180], [-90, 180], [90, 180], [90, -180], [-90, -180]],  # Mapa completo
                    bh_geojson['features'][0]['geometry']['coordinates'][0]  # O buraco com BH real
                ], color="black", fillColor="black", fillOpacity=0.7),
                dl.LayerGroup(id="markers-layer")
            ])
    ])

    # Callback que atualiza marcadores quando o usuário dá zoom e move o mapa
    @app.callback(
        Output("markers-layer", "children"),
        Input("map", "zoom"),
        Input("map", "bounds")
    )
    def update_markers(zoom, bounds):
        # Só exibe pontos se o zoom for alto o suficiente
        if not zoom or zoom < 16:
            return []
        if not bounds:
            return []

        (sw_lat, sw_lon), (ne_lat, ne_lon) = bounds
        children = []
        # Filtra apenas os pontos que estão dentro dos limites atuais do mapa
        for _, row in df.iterrows():
            lat, lon = row['coords']
            if sw_lat <= lat <= ne_lat and sw_lon <= lon <= ne_lon:
                nome = row['NOME_FANTASIA'] if pd.notna(row['NOME_FANTASIA']) and row['NOME_FANTASIA'].strip() else row['NOME']
                popup_html = f"""\
                    {nome} // 
                    Início: {row['DATA_INICIO_ATIVIDADE']} // 
                    Alvará: {'Sim' if str(row['IND_POSSUI_ALVARA']).upper() in ('1','S','SIM') else 'Não'} // 
                    {row['NOME_LOGRADOURO']}, {row['NUMERO_IMOVEL']} – {row['NOME_BAIRRO']}"""

                children.append(
                    dl.Marker(
                        position=[lat, lon],
                        children=[
                            dl.Tooltip(nome),
                            dl.Popup(popup_html)
                        ]
                    )
                )
        return children

    # Abre o browser e roda
    Timer(1, open_browser).start()
    app.run(debug=True)


if __name__ == '__main__':
    main()