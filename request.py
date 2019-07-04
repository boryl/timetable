import requests

def request():
	url = "https://pushdata.io"
	account = "bjorn-olle@vinnovera"
	series = "test"
	value = 1
	payload = {'account': account, 'series': series, 'value': value}
	r = requests.post(url, params=payload)
	print r.json()
	return r.json()


if __name__ == '__main__':
	request()