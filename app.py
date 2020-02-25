import json
from flask import Flask, request, make_response, jsonify
import requests
import pandas as pd
from scipy import spatial
import json
from string import Template
import os

app = Flask(__name__)
log = app.logger

headers = {'AccountKey': os.getenv("AccountKey"),
           'accept': 'application/json'}

card_tmpl_ = """{
"optionInfo": {
"key": "$key",
"synonyms": [
"$busstopcode",
"select $busstopcode",
"choose $busstopcode"
]
},
"description": "$description",
"image": {
"url": "$imageurl",
"accessibilityText": "first alt"
},
"title": "$description"
}
"""

carousel_tmpl_ = """{
"title": "$title",
"openUrlAction": {
    "url": "https://google.com"
},
"description": "$description",
"footer": "$footer",
"image": {
    "url": "https://developers.google.com/actions/assistant.png",
}
}"""

card_tmpl = Template(card_tmpl_)
carousel_tmpl = Template(carousel_tmpl_)

dfs = []
for i in range(0, 5500, 500):
    print(i)
    url = "http://datamall2.mytransport.sg/ltaodataservice/BusStops"
    url_ = (url+f'?$skip={i}')
    resp = requests.get(url_, headers=headers)
    df = pd.DataFrame(resp.json()['value'])
    dfs.append(df)
df_full = pd.concat(dfs)


@app.route('/', methods=['POST'])
def webhook():

   lat_ = 0
   long_ = 0

   req = request.get_json(silent=True, force=True)

   intent_name = req["queryResult"]["intent"]["displayName"]

   # Braching starts here
   if intent_name == 'Default Welcome Intent':
       print("Default Welcome Intent\n")
       response_text = "Hi buddy, I'am your bus assistant. I can help you with bus timings."

   elif intent_name == 'get_bus_stop':
       print("get_bus_stop\n")
       response_text = "i wish to know your location. is that ok ?. "
       return make_response(jsonify({
           'fulfillmentText': response_text,
           "fulfillmentMessages": [],
           "payload": {
               "google": {
                   "expectUserResponse": True,
                   "richResponse": {
                       "items": [
                           {
                               "simpleResponse": {
                                   "textToSpeech": "PLACEHOLDER"
                               }
                           }
                       ]
                   },
                   "userStorage": "{\"data\":{}}",
                   "systemIntent": {
                       "intent": "actions.intent.PERMISSION",
                       "data": {
                                 "@type": "type.googleapis.com/google.actions.v2.PermissionValueSpec",
                                 "optContext": "To address you by name and know your location",
                                 "permissions": [
                                     "NAME",
                                     "DEVICE_PRECISE_LOCATION"
                                 ]
                       }
                   }
               }
           }
       }))
   elif intent_name == 'permission_intent':
       print("permission_intent\n")
       ctx = getContext(req)
       status, name, lat, lon = get_lat_long(req)

       if status:
           busstop_list = getbusstops(lon, lat)
           for item in busstop_list:
               print(item[0], item[1])

           response_text = f" Hi {name} : you are at {lat}, {lon}. "
           return make_response(jsonify({
               'fulfillmentText': response_text,
               'outputContexts': list(ctx.values()),
               "fulfillmentMessages": [],
               "payload": {
                   "google": {
                       "expectUserResponse": True,
                       "richResponse": {
                                "items": [
                                    {
                                        "simpleResponse": {
                                            "textToSpeech": response_text
                                        }
                                    },
                                ]
                                },
                       "systemIntent": {
                           "intent": "actions.intent.OPTION",
                           "data": {
                               "@type": "type.googleapis.com/google.actions.v2.OptionValueSpec",
                               "listSelect": {
                                        "title": "Pick me your bustop, I will show you the busses available ",
                                        "items": [json.loads(card_tmpl.substitute(key="BSC_"+item[0], busstopcode=item[0], imageurl="https://cdn.iconscout.com/icon/premium/png-256-thumb/bus-stop-14-827026.png", description=item[1])) for item in busstop_list],
                               }
                           }
                       }
                   }
               }
           }))
       else:
           response_text = "permission denied"

   elif intent_name == 'option_intent':
       print("option_intent\n")
       print("*"*30)
    #    print(req)
       ctx = getContext(req)
       print(ctx["actions_intent_option"]["parameters"]["OPTION"])
       print("*"*30)
       print(ctx)

       if "BSC_"in ctx["actions_intent_option"]["parameters"]["OPTION"]:

           bus_stop_selected = (
               ctx["actions_intent_option"]["parameters"]["OPTION"])
           print("*"*30)
           bus_stop_selected = bus_stop_selected.split("_")[1]

           bus_list = getBusses(bus_stop_selected)

           if not bus_list:
                    response_text = (
                        f"Sorry, No bus is available at this time here in  : {bus_stop_selected} ☹")
           elif len(bus_list) == 1:
            #    to add a basic card
               timinglist = get_timing(bus_stop_selected, bus_list[0])
               response_text = "here you go..you hav one bus .." + \
                   " ".join(bus_list)
               if len(timinglist) == 1:
                   return make_response(jsonify({
                       'fulfillmentText': response_text,
                       # 'outputContexts': list(ctx.values()),
                       "fulfillmentMessages": [],
                       "payload": {
                           "google": {
                               "expectUserResponse": True,
                               "richResponse": {
                                   "items": [
                                        {
                                            "simpleResponse": {
                                                "textToSpeech": "Here is the list of Bus arrival timings"
                                            }
                                        },
                                        {
                                            "basicCard": {
                                                "title": "EstimatedArrival : " + timinglist[0]["EstimatedArrival"],
                                                "subtitle":"Bus Type : "+timinglist[0]["Type"] + " Bus Load : "+timinglist[0]["Load"],
                                                "formattedText": "",
                                                "image": {
                                                    "url": timinglist[0]["type_img"],
                                                    "accessibilityText": "Image alternate text"
                                                },
                                                "imageDisplayOptions": "CROPPED"
                                            }
                                        },

                                        ]
                               }
                           }
                       }

                   }))

               else:
                   return make_response(jsonify({
                       'fulfillmentText': response_text,
                       "fulfillmentMessages": [],
                       "payload": {
                           "google": {
                               "expectUserResponse": True,
                               "richResponse": {
                                   "items": [
                                        {
                                            "simpleResponse": {
                                                "textToSpeech": "Here is the list of Bus arrival timings"
                                            }
                                        },
                                        {
                                            "carouselBrowse": {
                                                "items": [{"title": "The next bus is arriving at -  "+item.get('EstimatedArrival'),
                                                           "openUrlAction": {
                                                    "url": "https://cdn.pixabay.com/photo/2019/02/19/19/45/thumbs-up-4007573_960_720.png"
                                                },
                                                    "description": item.get('Load'),
                                                    "footer": item.get('Type'),
                                                    "image": {
                                                    "url": item.get("type_img"),
                                                }
                                                } for item in timinglist]
                                            }
                                        }
                                        ]
                               }
                           }
                       }

                   }))

           else:
                    response_text = "here you go.." + " ".join(bus_list)
                    return make_response(jsonify({
                        'fulfillmentText': response_text,
                        "fulfillmentMessages": [],
                        "payload": {
                            "google": {
                                "expectUserResponse": True,
                                "richResponse": {
                                    "items": [
                                        {
                                            "simpleResponse": {
                                                "textToSpeech": response_text
                                            }
                                        },
                                    ]
                                },
                                "systemIntent": {
                                    "intent": "actions.intent.OPTION",
                                    "data": {
                                        "@type": "type.googleapis.com/google.actions.v2.OptionValueSpec",
                                        "listSelect": {
                                            "title": "Here you go..",
                                            "items": [json.loads(card_tmpl.substitute(key="BC_"+bus_stop_selected+":"+item, busstopcode=item, imageurl="https://img.freepik.com/free-vector/bus-logo-abstract_7315-17.jpg?size=626&ext=jpg", description=item)) for item in bus_list],
                                        }
                                    }
                                }
                            }
                        }
                    }))
       elif "BC_" in ctx["actions_intent_option"]["parameters"]["OPTION"]:
           ctx = getContext(req)
           print(ctx)
           bus_selected = (ctx["actions_intent_option"]
                           ["parameters"]["OPTION"])
           bus_selected = bus_selected.split("_")[1]
           b_code = bus_selected.split(":")[1]
           bs_code = bus_selected.split(":")[0]

           timinglist = get_timing(bs_code, b_code)

           response_text = "".join([f'Your next bus is at {item["EstimatedArrival"]} :: {item["Type"]} :: {item["Load"]} \n' for item in timinglist])
           print(response_text)

           if len(timinglist) == 1:
               return make_response(jsonify({
                   'fulfillmentText': response_text,
                   # 'outputContexts': list(ctx.values()),
                   "fulfillmentMessages": [],
                   "payload": {
                       "google": {
                           "expectUserResponse": True,
                           "richResponse": {
                                    "items": [
                                        {
                                            "simpleResponse": {
                                                "textToSpeech": "Here is the list of Bus arrival timings"
                                            }
                                        },
                                        {
                                            "basicCard": {
                                                "title": "EstimatedArrival : " + timinglist[0]["EstimatedArrival"],
                                                "subtitle":"Bus Type : "+timinglist[0]["Type"] + " Bus Load : "+timinglist[0]["Load"],
                                                "formattedText": "",
                                                "image": {
                                                    "url": timinglist[0]["type_img"],
                                                    "accessibilityText": "Image alternate text"
                                                },
                                                "imageDisplayOptions": "CROPPED"
                                            }
                                        },

                                    ]
                                    }
                       }
                   }

               }))

           else:
               return make_response(jsonify({
                   'fulfillmentText': response_text,
                   'outputContexts': list(ctx.values()),
                   "fulfillmentMessages": [],
                   "payload": {
                       "google": {
                           "expectUserResponse": True,
                           "richResponse": {
                                    "items": [
                                        {
                                            "simpleResponse": {
                                                "textToSpeech": "Here is the list of Bus arrival timings"
                                            }
                                        },
                                        {
                                            "carouselBrowse": {
                                                "items": [{"title": "The next bus is arriving at -  "+item.get('EstimatedArrival'),
                                                           "openUrlAction": {
                                                    "url": "https://cdn.pixabay.com/photo/2019/02/19/19/45/thumbs-up-4007573_960_720.png"
                                                },
                                                    "description": item.get('Load'),
                                                    "footer": item.get('Type'),
                                                    "image": {
                                                    "url": item.get("type_img"),
                                                }
                                                } for item in timinglist]
                                            }
                                        }
                                    ]
                                    }
                       }
                   }

               }))

   else:
       response_text = "No intent matched"
   # Branching ends here

   # Finally sending this response to Dialogflow.
   return make_response(jsonify({'fulfillmentText': response_text}))


# Handler  / functions for handling individual intents
def get_lat_long(req):
    ctx = getContext(req)
    if ctx["actions_intent_permission"]["parameters"]["PERMISSION"]:
        user_name = (req["originalDetectIntentRequest"]
                     ["payload"]["user"]["profile"]["displayName"])
        device = (req["originalDetectIntentRequest"]["payload"]["device"])
        lat_ = device["location"]["coordinates"]["latitude"]
        long_ = device["location"]["coordinates"]["longitude"]
        return(True, user_name, lat_, long_)
    else:
        return (False, '', 0, 0)


def getContext(req):
    ctx_tmp = {}
    for each_context in req["queryResult"]["outputContexts"]:
        ctx_tmp[each_context["name"].split("/")[-1]] = [each_context][0]
    return ctx_tmp


def get_busstop_coordinates():
    dfs = []
    for i in range(0, 5500, 500):
        print(i)
        url = "http://datamall2.mytransport.sg/ltaodataservice/BusStops"
        url_ = (url+f'?$skip={i}')
        resp = requests.get(url_, headers=headers)
        df = pd.DataFrame(resp.json()['value'])
        dfs.append(df)
    df_full = pd.concat(dfs)
    return df_full


def getbusstops(lon, lat):
    df_full_ = df_full
    pt = [lat, lon]
    A_ = df_full_[["BusStopCode", "Description"]].values
    A = df_full_[['Latitude', 'Longitude']].values
    kdtree = spatial.KDTree(A)
    distance, index = kdtree.query(pt, 15)
    top_busstops = A_[index].tolist()

    return top_busstops


def getresult(bus_stop):
    path = f'http://datamall2.mytransport.sg/ltaodataservice/BusArrivalv2?BusStopCode={bus_stop}'
    resp = requests.get(path, headers=headers)
    if resp.ok and len(resp.json().get("Services")) > 0:
        print("valid bus stop code ...")
        result = resp.json()
        return True, result
    else:
        print("No bus available / or invalid bus stop code")
        return False, ''


def getBusses(bus_stop):
    status, result = getresult(bus_stop)
    if status:
        if result["Services"]:
            bus_list = []
            for item in result["Services"]:
                bus_list.append(item["ServiceNo"])
            return bus_list
        else:
            return []
    else:
        return []


def get_timing(bs_code, b_code):
    url = f'http://datamall2.mytransport.sg/ltaodataservice/BusArrivalv2?BusStopCode={bs_code}&ServiceNo={b_code}'
    resp = requests.get(url, headers=headers)
    res = resp.json()
    item = res["Services"][0]
    listtemp = []
    if "NextBus" in item:
        if item["NextBus"]["EstimatedArrival"]:
            x = {}
            x["EstimatedArrival"] = item["NextBus"]["EstimatedArrival"].split('T')[
                1].split("+")[0]
            x["Load"] = func_1(item["NextBus"]["Load"])
            x["type_img"], x["Type"] = func_2(item["NextBus"]["Type"])
            listtemp.append(x)

    if "NextBus2" in item:
        if item["NextBus2"]["EstimatedArrival"]:
            x = {}
            x["EstimatedArrival"] = item["NextBus2"]["EstimatedArrival"].split('T')[
                1].split("+")[0]
            x["Load"] = func_1(item["NextBus2"]["Load"])
            x["type_img"], x["Type"] = func_2(item["NextBus2"]["Type"])
            listtemp.append(x)

    if "NextBus3" in item:
        if item["NextBus3"]["EstimatedArrival"]:
            x = {}
            x["EstimatedArrival"] = item["NextBus3"]["EstimatedArrival"].split('T')[
                1].split("+")[0]
            x["Load"] = func_1(item["NextBus3"]["Load"])
            x["type_img"], x["Type"] = func_2(item["NextBus3"]["Type"])
            listtemp.append(x)

    return listtemp


def func_1(load):
    if load == "SEA":
        return "Seats Available"
    elif load == "SDA":
        return "Standing Available"
    elif load == "LSD":
        return "Limited Standing"


def func_2(load):
    if load == "SD":
        return "https://cdn4.iconfinder.com/data/icons/veecons/512/bus_autobus-512.png", "Single Deck"
    elif load == "DD":
        return "https://st4.depositphotos.com/18664664/22486/v/1600/depositphotos_224861476-stock-illustration-double-decker-bus-icon-trendy.jpg", "Double Deck"
    elif load == "BD":
        return "https://static.turbosquid.com/Preview/001201/728/2R/citaro-g-euro-vi-model_0.jpg", "Bendy"


if __name__ == '__main__':
   app.run(debug=True, host='0.0.0.0', port=os.getenv("PORT"))
