import boto3
import time
import argparse
import json
from string import Template
from datetime import datetime, timedelta

QUERY = Template('''
fields @message
| filter @message like /$execution_arn/
| sort @timestamp asc
''')

def execute_query(log_group_name, execution_arn, start_time, end_time):
    client = boto3.client('logs')
    response = client.start_query(
        logGroupName=log_group_name,
        startTime=start_time,
        endTime=end_time,
        queryString=QUERY.substitute(execution_arn=execution_arn)
    )
    query_id = response['queryId']
    while True:
        response = client.get_query_results(queryId=query_id)
        if response['status'] not in ['Scheduled', 'Running']:
            break
        time.sleep(1)
    
    return response

def convert_timestamp(timestamp_str):
    timestamp = int(timestamp_str) / 1000.0
    return datetime.fromtimestamp(timestamp).isoformat()

def convert_logs_to_execution_history(query_response):
    events = []
    for entry in query_response['results']:
        log_entry = json.loads(entry[0]['value'])
        event = {
            "timestamp": convert_timestamp(log_entry['event_timestamp']),
            "type": log_entry['type'],
            "id": int(log_entry['id']),
            "previousEventId": int(log_entry['previous_event_id']),
        }
        
        details = log_entry['details']
        
        if log_entry['type'] == 'ExecutionStarted':
            event['executionStartedEventDetails'] = {
                "input": details['input'],
                "inputDetails": details['inputDetails'],
                "roleArn": details['roleArn']
            }
        elif log_entry['type'] in ['ChoiceStateEntered', 'TaskStateEntered']:
            event['stateEnteredEventDetails'] = {
                "name": details['name'],
                "input": details['input'],
                "inputDetails": details['inputDetails']
            }
        elif log_entry['type'] in ['ChoiceStateExited', 'TaskStateExited']:
            event['stateExitedEventDetails'] = {
                "name": details['name'],
                "output": details['output'],
                "outputDetails": details['outputDetails']
            }
        elif log_entry['type'] == 'TaskScheduled':
            event['taskScheduledEventDetails'] = {
                "resourceType": details['resourceType'],
                "resource": details['resource'],
                "region": details['region'],
                "parameters": details['parameters']
            }
        elif log_entry['type'] == 'TaskStarted':
            event['taskStartedEventDetails'] = {
                "resourceType": details['resourceType'],
                "resource": details['resource']
            }
        elif log_entry['type'] == 'TaskSucceeded':
            event['taskSucceededEventDetails'] = {
                "resourceType": details['resourceType'],
                "resource": details['resource'],
                "output": details['output'],
                "outputDetails": details['outputDetails']
            }
        elif log_entry['type'] == 'FailStateEntered':
            event['stateEnteredEventDetails'] = {
                "name": details['name'],
                "input": details['input'],
                "inputDetails": details['inputDetails']
            }
        elif log_entry['type'] == 'ExecutionFailed':
            event['executionFailedEventDetails'] = {}
        
        events.append(event)
    
    return {"events": events}

def main():
    parser = argparse.ArgumentParser(description='Query CloudWatch Logs for a specific execution ARN')
    
    parser = argparse.ArgumentParser(description='Query CloudWatch Logs for a specific execution ARN')
    parser.add_argument('--execution-arn', required=True, help='The execution ARN to search for in the logs')
    parser.add_argument('--log-group-name', required=True, help='The CloudWatch Logs group name')
    parser.add_argument('--end-time', type=int, default=int(datetime.now().timestamp() * 1000),
                        help='End time in Unix timestamp (milliseconds), by default it uses the time now')
    parser.add_argument('--start-time', type=int, 
                        default=int((datetime.now() - timedelta(hours=1)).timestamp() * 1000),
                        help='Start time in Unix timestamp (milliseconds), by default it uses the time 1 hour ago')
    args = parser.parse_args()

    query_response = execute_query(args.log_group_name, args.execution_arn, args.start_time, args.end_time)
    if query_response['status'] == 'Complete':
        express_history = convert_logs_to_execution_history(query_response)
        with open('output-express-history.json', 'w') as f:
            json.dump(express_history, f, indent=2)
        print("Execution history saved to 'output-express-history.json'")
    else:
        print(f"Query failed with status: {query_response['status']}")


if __name__ == '__main__':
    main()