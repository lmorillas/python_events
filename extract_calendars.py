#!/usr/bin/python2.4
# -*- coding: utf-8 -*-
#
# Copyright 2015 @lmorillas. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Based on
https://github.com/google/google-api-python-client/blob/master/samples/service_account/tasks.py
by jcgregorio@google.com


"""

__author__ = 'morillas@google.com (Luis Miguel Morillas)'

import httplib2
import pprint
import sys
import datetime
from operator import itemgetter
from itertools import groupby


from googleapiclient.discovery import build
from oauth2client.client import SignedJwtAssertionCredentials, AccessTokenRefreshError

from geopy import geocoders
google = geocoders.GoogleV3(timeout=5)
yandex = geocoders.Yandex(timeout=5)
nom = geocoders.Nominatim(timeout=5)


import shelve



# Credentials for Service Accout
EMAIL_CLIENT = '696801545616-44i6o78jdoa7me4lr416n1d5rniidmns@developer.gserviceaccount.com'
FILE_KEY = 'pycal.p12'

def connect_calendar():
    # Load the key in PKCS 12 format that you downloaded from the Google API
    # Console when you created your Service account.
    f = file(FILE_KEY, 'rb')
    key = f.read()
    f.close()

    credentials = SignedJwtAssertionCredentials(EMAIL_CLIENT,
          key,
          scope=['https://www.googleapis.com/auth/calendar',
               'https://www.googleapis.com/auth/calendar.readonly'])
    http = httplib2.Http()
    http = credentials.authorize(http)


    service = build(serviceName='calendar', version='v3', http=http)

    return service

def get_month(date_str):
    '''
    returns start month str from event
    '''
    return datetime.datetime.strptime(date_str[:10], '%Y-%m-%d').strftime("%B")


def calendar_events(service, cal_id, singleEvents="False"):
    # Today: only envents present and future
    timeMin = datetime.datetime.now().strftime('%Y-%m-%dT00:00:00.000Z')
    if singleEvents != "False":
        timeMax = '{}-12-31T23:00:00.000Z'.format(datetime.datetime.now().year)
    else:
        timeMax = None
    #timeMin = datetime.datetime.now().isoformat()
    events = []

    try:
        page_token = None
        while True:

            event_list = service.events().list(singleEvents=singleEvents,orderBy='startTime', calendarId=cal_id,
                    pageToken=page_token, timeMin=timeMin, timeMax=timeMax).execute()

            events.extend([event for event in event_list['items']])
            page_token = event_list.get('nextPageToken')
            if not page_token:
                break
    except AccessTokenRefreshError:
        print ('The credentials have been revoked or expired, please re-run'
          'the application to re-authorize.')
    return events


def geolocate(address):
    global geocache
    address = address.encode('utf-8')  # for storing in shelve
    loc = None
    if address not in geocache.keys():
        print 'Searching ', address
        try:
            loc = google.geocode(address)
        except:
            pass
        if not loc:
            try:
                loc = yandex.geocode(address)
            except:
                pass
            if not loc:
                try:
                    loc = google.geocode(','.join(address.split(',')[1:]))
                except:
                    pass
        if loc:
            loc = loc.latitude, loc.longitude, loc.raw
            geocache[address] = loc
    else:
        loc = geocache.get(address)[:2]
    return loc

def loc_to_country(latlon):
    global geocache
    if latlon not in geocache.keys():
        print 'Searching country of ', latlon
        try:
            loc = nom.reverse(latlon)
            if loc:
                country = loc.raw.get('address').get('country')
                geocache[latlon] = country
                return country
        except:
            return ''
    else:
        return geocache.get(latlon)


def event_to_item(event, cal):
    print event.get('summary').encode('utf-8'), ' --> ' ,
    item = {}
    item['description'] = event.get('description')
    item['id'] = event.get('id')
    item['start'] = event.get('start').get('date')
    if not item['start']:
        item['start'] = event.get('start').get('dateTime')
    item['end'] = event.get('end').get('date')
    if not item['end']:
        item['end'] = event.get('end').get('dateTime')
    item['label'] = event.get('summary')
    item['url'] = event.get('htmlLink')
    item['cal'] = cal
    item['month'] = get_month(item.get('start'))
    address = event.get('location')
    location = geolocate(address)
    if location:
        lat = location[0]
        lon = location[1]
        item['latlon'] = "{},{}".format(lat, lon)
        print item['latlon']
        country = loc_to_country(item['latlon'])
        item['country'] = country
    return item

def create_index():
    import pytz
    now = datetime.datetime.now(pytz.utc)
    format = "%Y-%m-%d %H:%M %Z"

    template = open('index.templ').read()
    open('index.html', 'w').write(template.format(datetime=now.strftime(format)))

def select_first_event(eventlist):
    '''select only the first enven when repeated events'''

    def sort_by_eventID(element):
        return element.get('recurringEventId')
    #recurring = itemgetter('recurringEventId')    # keyerror ?

    recurring = sort_by_eventID

    def _date(x):
        return x.get('start').get('dateTime')

    eventlist.sort(key=recurring)
    _non_repeated = []
    for ev, recur in groupby(eventlist, key=recurring):
        recur = sorted(recur, key=_date)
        _non_repeated.append(recur[0])  # only add the first

    return _non_repeated





if __name__ == '__main__':
    import datetime
    import json

    geocache = shelve.open('geocache.dat')


    # Cals IDs from https://wiki.python.org/moin/PythonEventsCalendar
    cal_id_python_events = 'j7gov1cmnqr9tvg14k621j7t5c@group.calendar.google.com'
    cal_id_user_group = '3haig2m9msslkpf2tn1h56nn9g@group.calendar.google.com'

    items = []

    service = connect_calendar()
    events = calendar_events(service, cal_id_python_events)

    for event in events:
        items.append(event_to_item(event, 'Larger'))


    events = calendar_events(service, cal_id_user_group, singleEvents="True")

    events = select_first_event(events)
    for event in events:
        items.append(event_to_item(event, 'Smaller'))


    geocache.sync()
    geocache.close()


    metadata = {"properties": {
        "url": {
            "valueType": "url"
        },
        "start": {
            "valueType": "date"
        },
        "end": {
            "valueType": "date"
        },
        "month": {
            "valueType": "date"
        },


    },
    "types": {
        "Item": {
            "pluralLabel": "events",
            "label": "event"
        }
    }}
    data = {'items': items}
    data.update(metadata)
    json.dump(data, open('events_python.json', 'w'))

    create_index()

