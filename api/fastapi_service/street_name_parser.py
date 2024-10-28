from re import search
from dadata import Dadata
from osmium.osm._osm import WayNodeList
token = "c9bd181f9fd147bbb8259a3765caa38b5b61f942"
regex = r",( (ул|пр) ([\w\s-]+))|( ([\w\s-]+) (пр-д|пл)),"


def parse_name(nodes_list : WayNodeList):
    dadata = Dadata(token)

    length = len(nodes_list)
    for i in range(0, length - 1):
        try:
            lat = (nodes_list[i].location.lat + nodes_list[i+1].location.lat) / 2
            lon = (nodes_list[i].location.lon + nodes_list[i+1].location.lon) / 2
        except:
            continue

        data = dadata.geolocate(name="address", lat=lat, lon=lon, count=1)
        if len(data) == 0:
            continue
        data = data[0].get('value')
        if data == None:
            continue
        match = search(regex, data)
        try:
            if match.group(2):
                street_type = match.group(2)
                if street_type == "ул":
                    street_name = match.group(3)+str(" улица")
                else:
                    street_name = str("проезд ")+match.group(3)
            elif match.group(6):
                street_type = match.group(6)
                if street_type == "пл":
                    street_name = match.group(5)+str(" площадь")
                else:
                    street_name = match.group(5)+str(" проезд")
            else:
                continue
            
            return street_name
        except:
            continue

    return '-'
