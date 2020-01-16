Butterbing Reporting Data Automation

A set of scripts in Python that access Butterbing data from the Unleashed Software API.

JSON Data is manipulated using Pandas - https://pandas.pydata.org/

Scripts are hosted in AWS Lambda and deployed using the Serverless Framework - https://serverless.com/

Note: Serverless build and deploy must be done on an Amazon Linux machine.

To setup new build environment:
  - Build machine must be Amazon Linux
  - Install Docker
  - Install Git
  - Install Node
  - Install serverless
  - Clone repo
  - Edit client_secret.json (from Google sheets worker account)
  - Edit confgit.py (from Unleashed Software Integration page)
  - Generate serverless packages with command $ serverless package

To Deploy Updates:
  - Config files and key pairs stored in S3 Bucket
  - Launch Build instance from AMI into Default VPC
  - SSH to new EC2 Instance
  - Navigate to local repo and 'git pull'
  - Copy config.py and client_secret.json
  - Deploy using 'sls deploy'
