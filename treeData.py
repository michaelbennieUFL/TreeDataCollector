import ee
import folium

ee.Authenticate()
ee.Initialize(project='ee-michaelalexanderbennie')

# 1. Load the image collection
collection = ee.ImageCollection('projects/ee-vasquezavicente/assets/BCI_50ha')
dates = collection.aggregate_array('system:time_start') \
                 .map(lambda d: ee.Date(d).format('YYYY-MM-dd')).getInfo()
print("Available Image Dates:", dates)

# 2. Pick an image
date = dates[-2]  # e.g. '2018-04-04'
image = collection.filterDate(date).first()

# 3. Visualization
vis_params = {'bands': ['b1','b2','b3'], 'min': 0, 'max': 255, 'gamma': 1}
region = image.geometry()
map_center = region.centroid().coordinates().getInfo()[::-1]
m = folium.Map(location=map_center, zoom_start=16)

# 4. Add the image layer
map_id_dict = image.getMapId(vis_params)
folium.TileLayer(
    tiles=map_id_dict['tile_fetcher'].url_format,
    attr='Google Earth Engine',
    overlay=True,
    name='Image Layer'
).add_to(m)

# 5. Load and filter crowns
crowns = ee.FeatureCollection('projects/ee-vasquezavicente/assets/BCI_50ha_crownmap_timeseries')

# If the crowns' "date" property is in the form "2018_04_04", replace hyphens:
crown_date = date.replace('-', '_')
filtered_crowns = crowns.filter(ee.Filter.eq('date', crown_date))

# Check how many crowns matched
count = filtered_crowns.size().getInfo()
print(f'Number of crowns for {crown_date}:', count)

# 6. Add the crowns to the map
folium.GeoJson(
    data=filtered_crowns.getInfo(),
    name='Crowns',
    style_function=lambda x: {
        'fillColor': 'transparent',
        'color': 'red',
        'weight': 1
    }
).add_to(m)

m.add_child(folium.LayerControl())
m.save('map.html')
print("Map saved to map.html")
