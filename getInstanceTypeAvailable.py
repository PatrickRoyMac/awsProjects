#!/usr/bin/env python3

import boto3
import csv
from botocore.exceptions import ClientError

class bcolors:
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

pricingclient = boto3.client('pricing', region_name='us-east-1')

paginator = pricingclient.get_paginator('get_attribute_values')

response_iterator = paginator.paginate(
    ServiceCode='AmazonEC2',
    AttributeName='instanceType',
    PaginationConfig={
        'MaxItems': 1000,
        'PageSize': 100
    }
)

InstanceTypes = []

for response in response_iterator:
    AttributeValues = response['AttributeValues']
    for AttributeValue in AttributeValues:
        if ("." in AttributeValue['Value']):
            InstanceTypes.append(AttributeValue['Value'])

ec2client = boto3.client('ec2')

response = ec2client.describe_regions(
)

RegionNames = []

Regions = response['Regions']
for Region in Regions:
    RegionNames.append(Region['RegionName'])

print(bcolors.OKGREEN + "Which region do you want to check for available Instance Types?" + bcolors.ENDC)
print(RegionNames)

SelectedRegion = input('Enter your region name: ')
if SelectedRegion not in RegionNames:
    print(bcolors.FAIL + "That is not a valid region" + bcolors.ENDC)
    exit()


print(bcolors.OKGREEN + "Searching", SelectedRegion + bcolors.ENDC)

ec2client = boto3.client('ec2', region_name=SelectedRegion)

x86Image = []
ArmImage = []

response = ec2client.describe_images(
    Filters=[
        {
            'Name': 'name',
            'Values': [
                'amzn2-ami-hvm-2.0.????????-x86_64-gp2',
            ]

        },
        {
            'Name': 'state',
            'Values': [
                'available',
            ]

        },
        {
            'Name': 'architecture',
            'Values': [
                'x86_64',
            ]

        }
    ],
    Owners=[
        'amazon',
    ]
)

Images = response['Images']
x86Image = Images[0]['ImageId']

response = ec2client.describe_images(
    Filters=[
        {
            'Name': 'name',
            'Values': [
                'amzn2-ami-hvm-2.0.????????-arm64-gp2',
            ]

        },
        {
            'Name': 'state',
            'Values': [
                'available',
            ]

        },
        {
            'Name': 'architecture',
            'Values': [
                'arm64',
            ]

        }
    ],
    Owners=[
        'amazon',
    ]
)

Images = response['Images']
if not Images:
    ArmImage = "NoArmImage"
else:
    ArmImage = Images[0]['ImageId']

response = ec2client.describe_availability_zones(
)

ZoneNames = []

AZs = response['AvailabilityZones']
for AZ in AZs:
    ZoneNames.append(AZ['ZoneName'])

SelectedSubnets = []

for Zone in ZoneNames:
    response = ec2client.describe_subnets(
        Filters=[
            {
                'Name': 'availability-zone',
                'Values': [
                    Zone,
                ]
            },
        ],
    )

    Subnets = response['Subnets']
    SelectedSubnets.append(Subnets[0])

FinalArray = []
FinalArray.append("AZ,InstanceType,Available,Reason")

for SelectedSubnet in SelectedSubnets:
    print(bcolors.WARNING + "Attempting to dry launch in " + str(SelectedSubnet['AvailabilityZone']) + bcolors.ENDC)
    for InstanceType in InstanceTypes:
        print(bcolors.WARNING + "Attempting to dry launch a(n) " + str(InstanceType) + bcolors.ENDC)
        if "a1." in InstanceType:
            if ArmImage == "NoArmImage":
                print("No Arm Instances in Region")
                print("Instance Type: " + str(InstanceType))
                print("Selected Image: No Arm Images in Region")
                FinalArray.append(str(SelectedSubnet['AvailabilityZone'])+","+str(InstanceType)+",No,Arm Instance Not In Region")
                continue
            else:
                SelectedImage = ArmImage
        else:
            SelectedImage = x86Image
        try:
            response = ec2client.run_instances(
                InstanceType=InstanceType,
                DryRun=True,
                SubnetId=SelectedSubnet['SubnetId'],
                MinCount=1,
                MaxCount=1,
                ImageId=SelectedImage
            )

            print(response)
        except ClientError as e:
            if e.response['Error']['Code'] == 'DryRunOperation':
                print("Dry Run Successful")
                FinalArray.append(str(SelectedSubnet['AvailabilityZone'])+","+str(InstanceType)+",Yes,Instance Available for Launch")
            elif e.response['Error']['Code'] == 'Unsupported':
                print("The requested configuration is currently not supported")
                print("Instance Type: " + str(InstanceType))
                print("Selected Image: " + str(SelectedImage))
                FinalArray.append(str(SelectedSubnet['AvailabilityZone'])+","+str(InstanceType)+",No,Instance Not Available in AZ or Region")
            elif e.response['Error']['Code'] == 'InsufficientInstanceCapacity':
                print("We currently do not have sufficient capacity in the Availability Zone you requested")
                print("Instance Type: " + str(InstanceType))
                print("Selected Image: " + str(SelectedImage))
                FinalArray.append(str(SelectedSubnet['AvailabilityZone'])+","+str(InstanceType)+",No,Insufficient Capacity")
            else:
                print("Unexpected error: %s" % e)

with open ('awsAvailibility.csv', 'w') as csvfile:
    csvwriter = csv.writer(csvfile)
    for row in FinalArray:
        csvwriter.writerow([row])

print(FinalArray)