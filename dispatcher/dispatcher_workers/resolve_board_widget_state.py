""" Resolve the states of the databox widget

"""

import asyncio

from aiohttp.helpers import current_task
import backoff
import dateutil.parser
import datetime
from envyaml import EnvYAML
import json
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport
import logging
import logging.config 
import os
import time

# EnvYAML necessary to parse environment vairables for the configuration file
config = EnvYAML("./docs/conf.yaml") 

# Logging
logging.config.dictConfig(config["logging"])
logger = logging.getLogger("alarms")

# Translating ui keys to python values for conditions operators
operators_dict = {'=': '==', '<': '<', '>': '>', '!=': '!=', 'contains': 'in'}

def typecasting(value):
    casted_value = value
    if casted_value == "true":
        casted_value = True
    elif casted_value == "false":
        casted_value = False
    elif type(casted_value) == type({"a": 1}):
        casted_value = str(casted_value)
    
    return casted_value

async def resolve_board_widget_state(event):
    """ 
    
    Args:
    =====
        event: json object
        
    Returns:
    ========
        none
        
    """
    try:
        
        logger.info(event)
        
        # GQL parameters
        gql_address = config['gql']['address']
        jwt_env_key = "JWT_ENV_DISPATCHER"
        jwt = os.environ[jwt_env_key]
        
        # GQL client
        transport = AIOHTTPTransport(url="http://{}/graphql".format(gql_address), headers={'Authorization': 'Bearer ' + jwt})
        client = Client(transport=transport, fetch_schema_from_transport=False)
        
        if 'objectId' not in event:
            return 0
        
        
        colors = [event['object']['color1'], event['object']['color2'], event['object']['color3']]
        colors = [c for c in colors if c != {}]
        current_color = event['object']['currentcolor']
        default_color = event['object']['color0']
        value = event['value']
        
        if len(colors) < 1:
            return 0
        
        #logger.info(alerts)
        
        colors_eval = [eval("{} {} {}".format(typecasting(value), operators_dict[c['operator']], typecasting(c['value']))) for c in colors]
        
        new_color = default_color
        for i, v in enumerate(colors_eval):
            if v == True:
                new_color = colors[i]['color']
        
        #logger.info(alerts_eval)
        
        if new_color != current_color:
            # Change to trigger and send notification
            optionsArrayPayload = "[{ groupName: \"Value\", property: \"Current color\", value: \"" + new_color + "\"}]"
            mutation_update_state = gql(
                """
                mutation UpdateWidgetColorState {{
                updateObjectPropertiesByName(input: {{
                    objectId: "{}"
                    transactionId: "{}"
                    propertiesArray: {}
                    }}){{
                        boolean
                    }}
                }}
                """.format(event['objectId'], round(time.time() * 1000), optionsArrayPayload)
            )
            mutation_update_state_result = await client.execute_async(mutation_update_state)
            #logger.info("🟢 Updated {}/{} alert status to {} on unlink property event.".format(event['object']['name'], event['object']['id'], status))
            # message = "Alert on widget {}".format(event['object']['name'])
            # spec = r'''{\"type\": \"WIDGET_ALERT\", \"alarm\": \"WIDGET_ITEM\"}'''
            # mutation_create_notification = gql(
            #     """
            #     mutation{{
            #         createNotification(input: {{
            #             notification: {{
            #                 subjectType: DATASET
            #                 subject: "{}"
            #                 subjectName: "{}"
            #                 tags: ["application", "board", "alert", "triggered"]
            #                 message: "{}"
            #                 spec: "{}"
            #                 }}
            #             }}){{
            #                     notification {{
            #                         id
            #                     }}
            #                 }}
            #             }}
            #     """.format(event['objectId'], event['object']['name'], message, spec)#format(event['object']['id'], event['object']['name'], message, spec)
            # )
            # result_create_notification = await client.execute_async(mutation_create_notification)
        # elif not any(alerts_eval) and alarm_status == 'triggered':
        #     # Change to on and send notification
        #     optionsArrayPayload = "[{ groupName: \"Status\", property: \"Alarm\", value: \"on\"}]"
        #     mutation_update_state = gql(
        #         """
        #         mutation UpdateWidgetAlarmState {{
        #         updateObjectPropertiesByName(input: {{
        #             objectId: "{}"
        #             transactionId: "{}"
        #             propertiesArray: {}
        #             }}){{
        #                 boolean
        #             }}
        #         }}
        #         """.format(event['objectId'], round(time.time() * 1000), optionsArrayPayload)
        #     )
        #     mutation_update_state_result = await client.execute_async(mutation_update_state)
            
        #     message = "Alert dismissed on widget {}".format(event['object']['name'])
        #     spec = r'''{\"type\": \"WIDGET_ALERT\", \"alarm\": \"WIDGET_ITEM\"}'''
        #     mutation_create_notification = gql(
        #         """
        #         mutation{{
        #             createNotification(input: {{
        #                 notification: {{
        #                     subjectType: DATASET
        #                     subject: "{}"
        #                     subjectName: "{}"
        #                     tags: ["application", "board", "alert"]
        #                     message: "{}"
        #                     spec: "{}"
        #                     }}
        #                 }}){{
        #                         notification {{
        #                             id
        #                         }}
        #                     }}
        #                 }}
        #         """.format(event['objectId'], event['object']['name'], message, spec)#format(event['object']['id'], event['object']['name'], message, spec)
        #     )
        #     result_create_notification = await client.execute_async(mutation_create_notification)
            
        return 0
            
    except Exception as e:
        logger.error("🔴 {}".format(e))

@backoff.on_exception(backoff.expo, Exception)
async def resolve_board_widget_state_subscription():
    """ Subscriptions on Pixel Board widgets
    
    Args:
    =====
        none
    
    Returns:
    ========
        none
        
    """
    try:
        # Grab async event loop
        loop = asyncio.get_event_loop()
        
        # GQL parameters
        gql_address = config['gql']['address']
        jwt_env_key = "JWT_ENV_DISPATCHER"
        jwt = os.environ[jwt_env_key]
        
        # GQL client
        transport = WebsocketsTransport(url="ws://{}/graphql".format(gql_address), headers={'Authorization': 'Bearer ' + jwt}, keep_alive_timeout=300)
        async with Client(
            transport=transport, fetch_schema_from_transport=False,
        ) as session:
            
            # GQL subscription for ...
            subscription = gql(
                """
                subscription ResolveBoardWidgetAlarms {
                    Objects(filterA: {
                        tags: ["application", "board", "widget", "databox"]
                        propertyChanged: [{groupName: "Value", property: "Value"}]
                    }){
                        event
                        relatedNode {
                                    ... on Object {
                                        id
                                        schemaType
                                        name
                                        enabled
                                        tags
                                        schemaId
                                    }
                                    ... on ObjectProperty {
                                        id
                                        objectId
                                        groupName
                                        property
                                        value 
                                        updatedAt
                                        linkedPropertyId
                                        object {
                                            id
                                            name
                                            enabled
                                            color0: property(propertyName: "Colors/Default color")
                                            color1: property(propertyName: "Colors/Color 1 condition")
                                            color2: property(propertyName: "Colors/Color 2 condition")
                                            color3: property(propertyName: "Colors/Color 3 condition")
                                            value: property(propertyName: "Value/Value")   
                                            currentcolor: property(propertyName: "Value/Current color")
                                        }      
                                    }
                                }
                            }
                        }
                """
            )
            
            logger.info("Dispatcher subscribed on board widget events.")
            
            # Send event to be processed by the worker
            async for event in session.subscribe(subscription):
                #logger.info(event)
                
                # Don't process deletion of monitor items
                if "delete" not in event['Objects']['event']:
                    # Find all the states tasks running for this monitor item and reset them if a new message is received
                    task_name = "resolve_board_widget_state_{}".format(event['Objects']['relatedNode']['objectId'])
                    tasks = [task for task in asyncio.all_tasks() if task.get_name() == task_name]
                    # If the tasks are already running cancel them
                    if len(tasks) > 0:
                        tasks[0].cancel()
                    
                    loop.create_task(resolve_board_widget_state(event['Objects']['relatedNode']), name=task_name)
                    
    except Exception as e:
        logger.error(e)    
    
    return 0

