import dash
import dash_leaflet as dl
from dash import html
import json
import webbrowser
from threading import Timer

# Carregar o GeoJSON real do polígono de Belo Horizonte
with open('belo_horizonte.geojson', 'r', encoding='utf-8') as f:
    bh_geojson = json.load(f)

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
               ], color="black", fillColor="black", fillOpacity=0.7)
           ])
])

def open_browser():
    webbrowser.open_new("http://127.0.0.1:8050/")

if __name__ == '__main__':
    Timer(1, open_browser).start()
    app.run(debug=True)