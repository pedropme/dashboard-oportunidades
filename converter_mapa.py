import geopandas as gpd

# carregar shp
gdf = gpd.read_file("maps/municipios.shp")

# simplificar geometria
gdf["geometry"] = gdf["geometry"].simplify(
    tolerance=0.01,
    preserve_topology=True
)

# salvar geojson leve
gdf.to_file(
    "maps/municipios.geojson",
    driver="GeoJSON"
)

print("GeoJSON criado com sucesso!")