from flask import Flask, render_template, request, redirect, url_for
from flask_caching import Cache
import datetime
import time
import requests
import random
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, SubmitField, RadioField, validators
#from slackclient import SlackClient
import json
from collections import defaultdict

cache = Cache()

application = Flask(__name__, instance_relative_config=True)
application.config.from_object('config')
application.config.from_pyfile('config.py')

cache.init_app(application)

#slack_client = SlackClient(application.config['SLACK_TOKEN'])

realtime_api_key = application.config['REALTIME_API_KEY']
stationsearch_api_key = application.config['STATIONSEARCH_API_KEY']


class stationsearchform(FlaskForm):
	search = StringField('Skriv in din sökning', [validators.Required('Du måste skriva något i fältet!')])
	submit = SubmitField('Sök')	

class configform(FlaskForm):
	timewindow = SelectField('minuter fram i tiden', [validators.NumberRange(min=5, max=60)], coerce=int)
	offset = SelectField('Visa avgångar mellan', [validators.NumberRange(min=0, max=30)], coerce=int)
	direction1 = BooleanField('Norr', default=True)
	direction2 = BooleanField('Söder', default=True)
	transport = RadioField('Färdmedel', choices = [('metro','tunnelbana'),('train','pendeltåg')], default='metro')
	submit = SubmitField('Skapa tidtabell')	


def templatecolor():
	colors = ['red','green','blue']
	color = colors[random.randint(0, 2)]
	return color

@cache.memoize(60)
def stationsearch(search):
	url = "https://api.sl.se/api2/typeahead.json"
	key = stationsearch_api_key
	payload = {'key': key, 'searchstring': search}
	r = requests.get(url, params=payload)
	return r.json()


@cache.memoize(60)
def SLrealtime(siteid, transport='metro', timewindow=60, offset=0, direction=False):
	url = "https://api.sl.se/api2/realtimedeparturesV4.json"
	key = realtime_api_key
	
	
	metro = 'true'
	bus = "false"
	train = "false"
	tram = "false"
	ship = "false"
	
	if(transport == 'train'):
		metro = 'false'
		train = 'true'
	
	null = False
	payload = {'key': key, 'siteid': siteid, 'timewindow': timewindow, 'metro': metro , 'bus': bus, 'train': train, 'tram': tram, 'ship': ship}
	r = requests.get(url, params=payload)
	return_json = r.json()
	
	d = {}
	
	if(transport == "metro"):
		response_key = "Metros"
	elif(transport == "train"):
		response_key = "Trains"
	
	for x in return_json['ResponseData'][response_key]:
		if(direction == False or direction == x['JourneyDirection']):
			
			GroupOfLineName = x['GroupOfLine'][:1].upper() + x['GroupOfLine'][1:]
			
			if(GroupOfLineName == "Tunnelbanans röda linje"):
				GroupOfLine = "red"
			elif(GroupOfLineName == "Tunnelbanans gröna linje"):
				GroupOfLine = "green"
			elif(GroupOfLineName == "Tunnelbanans blå linje"):
				GroupOfLine = "blue"
			elif(GroupOfLineName == "Pendeltåg"):
				GroupOfLine = "train"
			
			if(x['ExpectedDateTime']):
				timeString = return_json['ResponseData']['LatestUpdate'].split("T")
				now = timeString[1][:-3]
				ExpectedDateTime = x['ExpectedDateTime'].split("T")
			
				d1 = datetime.datetime.strptime(now, '%H:%M')
				d2 = datetime.datetime.strptime(ExpectedDateTime[1][:-3], '%H:%M')
			
				diff = int(divmod((d2-d1).total_seconds(), 60)[0])
			else:
				diff = 0
				ExpectedDateTime[1] = "XXX"		
			
			if(diff >= offset):
				if(x['DisplayTime'].endswith("min")):
					DisplayTime = x['DisplayTime']
				else:
					DisplayTime = ""
				
				toAppend = {'ExpectedDateTime': ExpectedDateTime[1][:-3], 'JourneyDirection': x['JourneyDirection'], 'Destination': x['Destination'], 'DisplayTime': DisplayTime, 'GroupOfLine': GroupOfLineName, 'Station': x['StopAreaName']}
		
				if(GroupOfLine not in d.keys()):
					d[GroupOfLine] = []
			
				d[GroupOfLine].append(toAppend)
	
	return d
  

def slackformat(json):
	
	json = {'blue': [{'ExpectedDateTime': '16:21', 'JourneyDirection': 1, 'Destination': 'Hjulsta', 'DisplayTime': '6 min', 'GroupOfLine': 'Tunnelbanans blå linje', 'Station': 'Duvbo'}, {'ExpectedDateTime': '16:21', 'JourneyDirection': 2, 'Destination': 'Kungsträdgården', 'DisplayTime': '6 min', 'GroupOfLine': 'Tunnelbanans blå linje', 'Station': 'Duvbo'}, {'ExpectedDateTime': '16:27', 'JourneyDirection': 2, 'Destination': 'Kungsträdgården', 'DisplayTime': '', 'GroupOfLine': 'Tunnelbanans blå linje', 'Station': 'Duvbo'}, {'ExpectedDateTime': '16:27', 'JourneyDirection': 1, 'Destination': 'Hjulsta', 'DisplayTime': '12 min', 'GroupOfLine': 'Tunnelbanans blå linje', 'Station': 'Duvbo'}, {'ExpectedDateTime': '16:33', 'JourneyDirection': 1, 'Destination': 'Hjulsta', 'DisplayTime': '18 min', 'GroupOfLine': 'Tunnelbanans blå linje', 'Station': 'Duvbo'}, {'ExpectedDateTime': '16:33', 'JourneyDirection': 2, 'Destination': 'Kungsträdgården', 'DisplayTime': '', 'GroupOfLine': 'Tunnelbanans blå linje', 'Station': 'Duvbo'}, {'ExpectedDateTime': '16:39', 'JourneyDirection': 1, 'Destination': 'Hjulsta', 'DisplayTime': '', 'GroupOfLine': 'Tunnelbanans blå linje', 'Station': 'Duvbo'}, {'ExpectedDateTime': '16:39', 'JourneyDirection': 2, 'Destination': 'Kungsträdgården', 'DisplayTime': '', 'GroupOfLine': 'Tunnelbanans blå linje', 'Station': 'Duvbo'}]}
	d = {}
	
	d["text"] = json['blue'][0]['GroupOfLine']
	d["callback_id"] = "change_line"
	d["color"] = "color"
	d["attachment_type"] = "default"
	d["fields"] = []
	d["fields"].append({"title": "title"})
	
	
	print(d)
	
	return d	

@application.route("/", methods=['GET', 'POST'])
def startsearch():
	
	form = stationsearchform()
	
	if form.validate_on_submit():
		search = form.search.data
		stations = stationsearch(search)
	else:
		stations = ""
	
	templateData = {
		'stations': stations,
		'line': templatecolor(),
		'title': "Sök station"
	}
	
	return render_template('stationsearch.html', **templateData, form=form)

@application.route("/config/<int:station>/", methods=['GET', 'POST'])
def config(station=0):
	
	form = configform()
	
	timewindow = 60
	offset = 30
	
	form.timewindow.choices = [(n, n) for n in range(5,timewindow+1,5)]
	form.timewindow.data = timewindow
	form.offset.choices = [(n, n) for n in range(0,offset+1,5)]
	
	if form.validate_on_submit():
		timewindow = form.timewindow.data
		offset = form.offset.data
		transport = form.transport.data
		direction1 = form.direction1.data
		direction2 = form.direction2.data
		direction = 0
		if (direction1 and not direction2):
			direction = 1
		elif (direction2 and not direction1):
			direction = 2
		
		return redirect(url_for('timetable', station = station, transport = transport, timewindow=timewindow, offset=offset, direction=direction))
		
	templateData = {
		'station': station,
		'line': templatecolor(),
		'title': "Skapa tidtabell"
	}
	
	return render_template('config.html', **templateData, form=form)
	
@application.route("/<int:station>/")
@application.route("/<int:station>/<string:transport>/")
@application.route("/<int:station>/<string:transport>/<int:timewindow>/<int:offset>/<int:direction>/")
@application.route("/<int:station>/<string:transport>/<int:timewindow>/<int:offset>/<int:direction>/<string:line>/")
def timetable(station, transport="metro", timewindow=60, offset=0, direction=False, line=0):
		
		#9324 - Duvbo
		# 2 - South
		response = SLrealtime(station, transport, timewindow, offset, direction)
		if(not response):
			response = {'noresponse': 'true'}
		lines = [*response]	
		
		
		if(lines and line == 0):
			line = lines[0]

		links = {}
		
		if(len(lines) > 1):
			for i in lines:
				if(i != line):
					links[i] = url_for('timetable',station=station,transport=transport,timewindow=timewindow,offset=offset,direction=direction,line=i)
		
		templateData = {
			'departures': response,
			'line': line,
			'links': links,
			'title': "Tidtabell för"
		}

		return render_template('timetable.html', **templateData)


@application.route("/slack/message_actions/", methods=['POST'])
def slackresponse():
  if request.method == 'POST':
      data = json.loads(request.form["payload"]) # a multidict containing POST data
      print(data['response_url'])
      slackjson = {"text":"Tidtabell för STATION","attachments":[{"text":"Röda linjen","callback_id":"change_line","color":"#LINE","attachment_type":"default","fields":[{"title":"Volume","value":"1","short":'true'},{"title":"Issue","value":"3","short":'true'}],"actions":[{"name":"line","text":"LINE1","type":"button","value":"LINE1"},{"name":"line","text":"LINE2","type":"button","value":"LINE2"}]}]}
      response = requests.post(
        data['response_url'], json=slackjson,
        headers={'Content-Type': 'application/json'}
      )
      
      
      return (""), 200
      
      """
      ImmutableMultiDict(
      [('payload', 
      '{
      "type":"interactive_message",
      "actions":[{"name":"line","type":"button","value":"LINE1"}],
      "callback_id":"change_line",
      "team":{"id":"T57BCRDNW","domain":"technodome"},
      "channel":{"id":"D56M4H0L8","name":"directmessage"},
      "user":{"id":"U585HG3FG","name":"bjornolle"},
      "action_ts":"1521029029.061055",
      "message_ts":"1521029024.000063",
      "attachment_id":"1",
      "token":"LXNVA6uYN5pUe6Gd1f4VYkQC",
      "is_app_unfurl":false,
      "response_url":"https:\\/\\/hooks.slack.com\\/actions\\/T57BCRDNW\\/330766078919\\/d2wpR5qgfSL4tT6eJ4v91rzf",
      "trigger_id":"330561887446.177386863778.314551fb4e48c2da763c5c1b6f42ef3c"}')])
      """


@application.route("/slack/timetable/", methods=['POST'])
def slackslash():
    if request.method == 'POST':
        data = request.form # a multidict containing POST data
        
        stationresponse = stationsearch(data['text'])
        #print(stationresponse['ResponseData'][0]['SiteId'])
        
        timetableresponse = SLrealtime(stationresponse['ResponseData'][0]['SiteId'], "metro", 30, 5)
        #print(timetableresponse)
        
        slackjson = slackformat('test')
        
        slackjson = {"text": "Tidtabell för *" + stationresponse['ResponseData'][0]['Name'] + "*","attachments":[{"text":"station","callback_id":"change_line","color":"#LINE","attachment_type":"default","fields":[{"title":"Volume","value":"1","short":'true'},{"title":"Issue","value":"3","short":'true'}],"actions":[{"name":"line","text":"LINE1","type":"button","value":"LINE1"},{"name":"line","text":"LINE2","type":"button","value":"LINE2"}]}]}
        response = requests.post(
          data['response_url'], json=slackjson,
          headers={'Content-Type': 'application/json'}
        )
        return (""), 200
	
"""
ImmutableMultiDict(
        [
        ('token', 'LXNVA6uYN5pUe6Gd1f4VYkQC'), 
        ('team_id', ' '), 
        ('team_domain', 'technodome'), 
        ('channel_id', 'D56M4H0L8'), 
        ('channel_name', 'directmessage'), 
        ('user_id', 'U585HG3FG'), 
        ('user_name', 'bjornolle'), 
        ('command', '/tidtabell'), 
        ('text', 'test'), 
        ('response_url', 'https://hooks.slack.com/commands/T57BCRDNW/328827035089/8JWL67Ou6Cei1MqAPpzZ7Bh9'), 
        ('trigger_id', '329380841282.177386863778.f2674c9512cf559147dda5c04682fa1a')])        
"""

@application.errorhandler(404)
def page_not_found(e):
	return render_template('404.html', title="404"), 404

@application.errorhandler(500)
def application_error(e):
	return render_template('500.html', title="500"), 500


if __name__ == '__main__':
	application.run(application)