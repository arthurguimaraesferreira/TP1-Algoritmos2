import dash
import dash_leaflet as dl
from dash import html
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


    # Plotar os bares no pontos especificados de latitude e longitude
    df = pd.read_csv('bares_restaurantes_reduzido.csv')
    df['coords'] = df['GEOMETRIA'].apply(parse_point)

    markers = []
    for _, row in df.iterrows():
        # 1) escolhe o nome a exibir
        nome_exibir = row['NOME_FANTASIA'] if pd.notna(row['NOME_FANTASIA']) and row['NOME_FANTASIA'].strip() else row['NOME']

        # 2) formata o endereço completo
        endereco = f"Endereço: {row['NOME_LOGRADOURO']}, {row['NUMERO_IMOVEL']}"
        if pd.notna(row['COMPLEMENTO']) and row['COMPLEMENTO'].strip():
            endereco += f" – {row['COMPLEMENTO']}"
        endereco += f" – Bairro {row['NOME_BAIRRO']}"

        # 3) converte indicador de alvará em texto
        possui_alvara = 'Sim' if str(row['IND_POSSUI_ALVARA']).upper() in ('1','S','SIM','TRUE') else 'Não'

        # 4) monta o conteúdo do popup
        popup_content = html.Div([
            html.B(nome_exibir), html.Br(),
            f"Início da atividade: {row['DATA_INICIO_ATIVIDADE']}", html.Br(),
            f"Possui alvará: {possui_alvara}", html.Br(),
            endereco
        ])

        # 5) adiciona Tooltip + Popup no Marker
        markers.append(
            dl.Marker(
                position=row['coords'],
                children=[
                    dl.Tooltip(nome_exibir),
                    dl.Popup(popup_content)
                ]
            )
        )


    # Criar app
    app = dash.Dash(__name__)

    app.layout = html.Div([
        dl.Map(center=[-19.9191, -43.9386], zoom=12, style={'width': '100%', 'height': '500px'},
            children=[
                dl.TileLayer(),  # Camada base (pode ajustar ou remover)
                # Mostrar o polígono real
                dl.GeoJSON(data=bh_geojson, style={"color": "blue", "weight": 2, "fillOpacity": 0.1}),
                # Máscara para áreas fora do polígono real
                dl.Polygon(positions=[
                    [[-90, -180], [-90, 180], [90, 180], [90, -180], [-90, -180]],  # Mapa completo
                    bh_geojson['features'][0]['geometry']['coordinates'][0]  # O buraco com BH real
                ], color="black", fillColor="black", fillOpacity=0.7),
                dl.LayerGroup(markers)
            ])
    ])

    # Abre o browser e roda
    Timer(1, open_browser).start()
    app.run(debug=True)


if __name__ == '__main__':
    main()