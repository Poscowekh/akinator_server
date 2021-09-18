import requests


data = {
    "request_type": "fetch_update",
    "theme": "animals",
    "version": "1.0.0",
    "data": []
    }
response = requests.post("http://localhost:8000", json=data)
json = response.json()
headers = response.headers
print("HEADERS")
for i in headers:
    print(f"{i}: {headers[i]}")
print("JSON")
for i in json:
    print(f"{i}: {json[i]}")
#for i in received:
#    print(f"{i}: {received[i]}")
