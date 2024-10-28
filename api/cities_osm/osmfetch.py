import requests
import osmnx as ox

def osmfetch(title, bbox, save_directory, expansion = 0) -> str:
    """
    Fetches osm data with api call using bbox and saving it in save_dir;
    Bbox coordinates order = [south,west,north,east];
    Optional expansion (in percents) modifies bbox area;
    Returns full path to the datafile
    """
    useragent = 'Urban-Topology-Analysis-Service/api'
    headers = {
        'Connection': 'keep-alive',
        'sec-ch-ua': '"Not-A.Brand";v="99", "Opera";v="91", "Chromium";v="105"',
        'Accept': '*/*',
        'Sec-Fetch-Dest': 'empty',
        'User-Agent': useragent,
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://overpass-turbo.eu',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'cors',
        'Referer': 'https://overpass-turbo.eu/',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'dnt': '1',
    }

    width = bbox[2] - bbox[0] #модифицируем bbox в соответствии с expansions
    height = bbox[3] - bbox[1]
    bbox[0] -= round(expansion/200 * width,8)
    bbox[1] -= round(expansion/200 * height,8)
    bbox[2] += round(expansion/200 * width,8)
    bbox[3] += round(expansion/200 * height,8)

    query = f"nwr ({bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]});out geom;""" #запрос для получения данных
    data = {
    'data': query
    }
    response = requests.post('https://overpass-api.de/api/interpreter', headers=headers, data=data)
    if response.status_code != 200:
        title=f'status_code_{response.status_code}' # сохраняем файл с именем статус кода при ошибочном ответе api

    full_path = f'{save_directory}/{title}.osm'

    with open(full_path, 'w', encoding="utf-8") as f:
        f.write(response.text)
        
    return full_path

def download_city(city_name : str) -> str:
    filePath = './'
    extension = 10

    print(f'Loading: {filePath}')
    query = {'city': city_name}
    try:
        city_info = ox.geocode_to_gdf(query)

        city_info.plot()

        north = city_info.iloc[0]['bbox_north']  
        south = city_info.iloc[0]['bbox_south']
        east = city_info.iloc[0]['bbox_east'] 
        west = city_info.iloc[0]['bbox_west']

        return osmfetch(city_name, [south, west, north, east], filePath, extension)
    except ValueError:
        print('Invalid city name')
        return None

