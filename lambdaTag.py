Terminating non compliant ec2 instances based on tags and Lambda


Tagging is one of the best practices recommended by so many experts but it is also one of the most ignored strategies when it comes to creating an architecture. Adding tags to your resources is simple, but extremely critical part when it comes to management of these resources. When used intelligently, tagging can streamline deployments.
With the number of services that AWS offers, it's easy to lose track of what you are using, who owns it, and how much it might cost. AWS has come up with a 20+ paged document to enlist the best practices for tagging which can be found below. 



A simple start would be to check all the EC2 instances that is being provisioned for a particular tag and delete them straight away if the tag does not exist. This can be achieved using a combination of cloudtrail , s3, Lamdba and SNS. The below diagram roughly represents what we are trying to achieve here.
When the user creates an EC2 instance without the appropriate tags, Cloudtrail records API calls made on your account and delivers
log files to your Amazon S3 bucket which in turn triggers a lambda function that deletes this instance and sends an email notification via SNS.
We need to create a Cloudtrail trail via the CLI or the web console. When you create this trail you can also create a s3 bucket when using the console but if you are using the CLI, then you have to create a S3 bucket separately.
aws cloudtrail create-trail --name tagtrail--s3-bucket-name tag-bucket --is-multi-region-trail
Next, create a SNS topic and subscribe to it, in order to receive notifications via email. Once the topic is create, please note down the arn which would be something like ( arn:aws:sns:region:xxxxx:tag-topic ). This arn will be used in later on.
aws sns create-topic –name tag-topic
For our Lambda function to work, it has to interact with s3 , sns etc and hence we need to create a role for it. In short, create a policy first with the permissions and then create a Lambda role and attach the policy to it. You can use the following policy and insert the proper SNS arn 



To create the lambda function select the 'Author from scratch' option , give it a name and select python 2.7 as the runtime. In the Designer section add a trigger and select amazon S3. Use the bucket that you created with cloudtrail. The destination should be the SNS topic that you created. In the function code, directly copy paste the following code and replace the ARN and COMPLIANT_TAGS .
from __future__ import print_function
import json
import urllib
import boto3
import gzip
import io
s3 = boto3.client('s3')
sns = boto3.client('sns')
SNS_ARN = 'arn:aws:sns:ap-northeast-2:132323974198:ec2taggingmonitor'
COMPLIANT_TAGS = ['LOL', 'GGG', 'BRB', 'YLO']
def decompress(data):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
        return f.read()
def report(instance, user, region):
    report = "User " + user + " created an instance with non-compliant tag in the region " +  region + ". \n"
    report += "Instance id: " + instance['instanceId'] + "\n"
    report += "Instance type: " + instance['instanceType'] + "\n"
    report += "The instance is being destroyed."
    return report
def lambda_handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.unquote_plus(event['Records'][0]['s3']['object']['key'].encode('utf8'))
    try:
        s3_object = s3.get_object(Bucket=bucket, Key=key)
        s3_object_content = s3_object['Body'].read()
        s3_object_unzipped_content = decompress(s3_object_content)
        json_object = json.loads(s3_object_unzipped_content)
        for record in json_object['Records']:
            if record['eventName'] == "RunInstances":
                user = record['userIdentity']['userName']
                region = record['awsRegion']
                ec2 = boto3.resource('ec2', region_name=region)
                for index, instance in enumerate(record['responseElements']['instancesSet']['items']):
                    instance_object = ec2.Instance(instance['instanceId'])
                    tags = {}
                    for tag in instance_object.tags:
                        tags[tag['Key']] = tag['Value']
                    if('Owner' not in tags or tags['Owner'] not in COMPLIANT_TAGS):
                        instance_object.terminate()
                        sns.publish(TopicArn=SNS_ARN, Message=report(instance, user, region))
    except Exception as e:
        print(e)
        raise e
