#Unleashed API - Invoices Export Version 1.3

#Python 3.7
#Local packages: pip install -r requirements.txt
import requests
import json
import hmac
import hashlib
import base64
import config as cfg
import time
import pandas as pd
from pandas import DataFrame
from pandas.io.json import json_normalize
import pygsheets
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

#Wrap everything in a function for lambda to execute.
def lambda_handler(event, context):
    #Script startup.
    starttime = datetime.now()

    #Unleashed API details.
    api_id = cfg.unleashed_api_id
    api_key = cfg.unleashed_api_key
    api_url = "https://api.unleashedsoftware.com/"

    #Unleashed API endpoint inputs.
    endpoint = "SalesOrders"
    query_key = "?"
    query = "startDate=2020-09-10" #note: Account was created on 09/10/20 - no data exists before then.

    #The method signature must be generated by taking the query string, and creating a HMAC-SHA256 signature using your API key as the secret key.
    digest = hmac.new(key=api_key.encode('utf-8'),msg=query.encode('utf-8'),digestmod=hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode()

    if not query:
    	request_url = api_url + endpoint
    else:
    	request_url = api_url + endpoint + query_key + query
    request_headers = {
    	'api-auth-id': api_id,
    	'Content-Type': 'application/json',
    	'Accept': 'application/json',
    	'api-auth-signature': signature
    }
    #Send the request for the first page.
    response = requests.get(url=request_url, headers=request_headers)

    sales_orders_parsed = response.json()
    pagination = sales_orders_parsed['Pagination']
    order_data = sales_orders_parsed['Items']
    sales_order_lines = order_data,['SalesOrderLines']

    number_of_items = pagination.get('NumberOfItems')
    number_of_pages = pagination.get('NumberOfPages')
    number_of_orders = len(order_data)

    #Set initial PageNumber for the loop below.
    page_number = pagination.get('PageNumber') - 1
    if number_of_pages == 1:
    	print("Importing " + str(number_of_items) + " Sales Orders from " + str(number_of_pages) + " page.")
    else:
    	print("Importing " + str(number_of_items) + " Sales Orders from " + str(number_of_pages) + " pages.")

    #The API limits JSON results to 200 items per page, so this loops as many times as there are pages.
    main_dataframe_list = []
    sales_order_lines_dataframe_list = []
    while page_number < number_of_pages:
    	page_number +=1
    	if not query:
    		request_url = api_url + endpoint + "/" + str(page_number)
    	else:
    		request_url = api_url + endpoint + "/" + str(page_number) + "/" + query_key + query
    	response = requests.get(url=request_url, headers=request_headers)
    	sales_orders_parsed = response.json()
    	order_data = sales_orders_parsed['Items']
    	number_of_orders = len(order_data)
    	print("Writing page " + str(page_number) + " of " + str(number_of_pages) + " from " + request_url)

    	#Normalize the nested SalesOrders data and retrieve OrderNumber to be used as the dataframe's index.
    	sales_order_lines_dataframe = []
    	for s in range(number_of_orders):
    		d = pd.io.json.json_normalize(order_data[s]['SalesOrderLines'])
    		d['OrderNumber'] = order_data[s]['OrderNumber']
    		sales_order_lines_dataframe.append(d)
    	sales_order_lines_dataframe = pd.concat(sales_order_lines_dataframe, sort=False)
    	sales_order_lines_dataframe.set_index('OrderNumber')

    	#Normalize the rest of the order_data, drop unneeded columns and set OrderNumber as the index for merging later.
    	main_dataframe = pd.io.json.json_normalize(order_data)
    	main_dataframe.set_index('OrderNumber')
    	main_dataframe.drop(labels=['AllocateProduct', 'BCSubTotal', 'BCTaxTotal', 'BCTotal', 'Comments', 'CompletedDate',	'CreatedBy', 'CreatedOn', 'Currency.CurrencyCode', 'Currency.Description', 'Currency.Guid', 'Currency.LastModifiedOn', 'Customer.CurrencyId', 'Customer.Guid', 'Customer.LastModifiedOn', 'CustomerRef', 'DeliveryCity', 'DeliveryCountry', 'DeliveryInstruction', 'DeliveryMethod', 'DeliveryPostCode', 'DeliveryStreetAddress', 'DeliveryStreetAddress2', 'DeliverySuburb', 'DiscountRate', 'ExchangeRate',	'Guid',	'LastModifiedBy', 'LastModifiedOn', 'PaymentDueDate', 'ReceivedDate', 'SalesOrderLines', 'SalesOrderGroup', 'SendAccountingJournalOnly', 'SourceId', 'SubTotal', 'Tax.CanApplyToExpenses', 'Tax.CanApplyToRevenue', 'Tax.Description', 'Tax.Guid', 'Tax.LastModifiedOn', 'Tax.Obsolete', 'Tax.TaxCode', 'Tax.TaxRate', 'TaxRate', 'TaxTotal', 'Total', 'TotalVolume', 'TotalWeight', 'Warehouse.AddressLine1', 'Warehouse.AddressLine2', 'Warehouse.City', 'Warehouse.ContactName', 'Warehouse.Country', 'Warehouse.DDINumber', 'Warehouse.FaxNumber', 'Warehouse.Guid', 'Warehouse.IsDefault', 'Warehouse.LastModifiedOn', 'Warehouse.MobileNumber', 'Warehouse.Obsolete', 'Warehouse.PhoneNumber', 'Warehouse.PostCode', 'Warehouse.Region', 'Warehouse.StreetNo', 'Warehouse.Suburb', 'Warehouse.WarehouseCode', 'XeroTaxCode'], axis=1,inplace = True)
    	sales_order_lines_dataframe.drop(labels=['AverageLandedPriceAtTimeOfSale', 'BCLineTax', 'BCUnitPrice', 'BCLineTotal', 'BatchNumbers', 'SerialNumbers', 'TaxRate', 'UnitPrice', 'Volume', 'Weight', 'XeroSalesAccount', 'XeroTaxCode', 'Comments', 'DiscountRate', 'DueDate', 'Guid', 'LastModifiedOn', 'LineNumber', 'LineTax', 'LineTaxCode', 'LineType', 'Product.Guid'], axis=1,inplace = True)

    	#Append this loop's dataframes to the main dataframe list for concatenation later.
    	main_dataframe_list.append(main_dataframe)
    	sales_order_lines_dataframe_list.append(sales_order_lines_dataframe)

    #Concatenate the dataframes lists built during the loops.
    main_dataframe = pd.concat(main_dataframe_list, sort=False)
    sales_order_lines_dataframe = pd.concat(sales_order_lines_dataframe_list, sort=False)

    #Merge the two dataframes using OrderNumber as the entry point.
    dataframe = pd.merge(main_dataframe, sales_order_lines_dataframe, on='OrderNumber', how='left')

    #Map columns and reorder them as necessary.
    print("Rearranging data...")
    OrderNumber = dataframe['OrderNumber']
    dataframe.drop(labels=['OrderNumber'], axis=1,inplace = True)
    dataframe.insert(0, 'Order Number', OrderNumber)

    OrderDate = dataframe['OrderDate']
    dataframe.drop(labels=['OrderDate'], axis=1,inplace = True)
    dataframe.insert(1, 'Order Date', OrderDate)

    RequiredDate = dataframe['RequiredDate']
    dataframe.drop(labels=['RequiredDate'], axis=1,inplace = True)
    dataframe.insert(2, 'Required Date', RequiredDate)

    CustomerCode = dataframe['Customer.CustomerCode']
    dataframe.drop(labels=['Customer.CustomerCode'], axis=1,inplace = True)
    dataframe.insert(3, 'Customer Code', CustomerCode)

    CustomerName = dataframe['Customer.CustomerName']
    dataframe.drop(labels=['Customer.CustomerName'], axis=1,inplace = True)
    dataframe.insert(4, 'Customer', CustomerName)

    DeliveryName = dataframe['DeliveryName']
    dataframe.drop(labels=['DeliveryName'], axis=1,inplace = True)
    dataframe.insert(5, 'Customer Delivery Address Name', DeliveryName)

    ProductCode = dataframe['Product.ProductCode']
    dataframe.drop(labels=['Product.ProductCode'], axis=1,inplace = True)
    dataframe.insert(6, 'Product Code', ProductCode)

    ProductDescription = dataframe['Product.ProductDescription']
    dataframe.drop(labels=['Product.ProductDescription'], axis=1,inplace = True)
    dataframe.insert(7, 'Product', ProductDescription)

    WarehouseName = dataframe['Warehouse.WarehouseName']
    dataframe.drop(labels=['Warehouse.WarehouseName'], axis=1,inplace = True)
    dataframe.insert(8, 'Warehouse', WarehouseName)

    OrderStatus = dataframe['OrderStatus']
    dataframe.drop(labels=['OrderStatus'], axis=1,inplace = True)
    dataframe.insert(9, 'Status', OrderStatus)

    OrderQuantity = dataframe['OrderQuantity']
    dataframe.drop(labels=['OrderQuantity'], axis=1,inplace = True)
    dataframe.insert(10, 'Quantity', OrderQuantity)

    LineTotal = dataframe['LineTotal']
    dataframe.drop(labels=['LineTotal'], axis=1,inplace = True)
    dataframe.insert(11, 'Sub Total', LineTotal)

    DeliveryRegion = dataframe['DeliveryRegion']
    dataframe.drop(labels=['DeliveryRegion'], axis=1,inplace = True)
    dataframe.insert(12, 'State', DeliveryRegion)

    #Bug fix: Sales person is being dropped here because of a bug that seems to have developed since 09/02/19 with the way 'SalesPerson' data is being read. It looks like [null] data from the API causes the problem.
    dataframe.drop(labels=['SalesPerson'], axis=1,inplace = True)
    #Bug fix: 16/01/2020 More labels being dropped here because they stopped working in the big drop line above.
    #Bug fix: 17/01/2021 Labels in the line below are no longer found, and thus can't be dropped so script errors when trying to refer to them. Commenting out this line completely works as these labels don't exists anyway.
    #dataframe.drop(labels=['SalesPerson.Email', 'SalesPerson.FullName', 'SalesPerson.Guid', 'SalesPerson.LastModifiedOn', 'SalesPerson.Obsolete',], axis=1,inplace = True)

    #Parse timestamps
    def parse_timestamp(string):
    	pattern = "/Date\(|\)/"
    	pattern = re.compile(pattern)
    	try:
    		timestamp = pattern.sub(
    			string = string,
    			repl = ""
    		)
    		return datetime.fromtimestamp(int(timestamp)/1000)
    	except:
    		return None
    dataframe['Order Date'] = dataframe['Order Date'].apply(parse_timestamp)
    dataframe['Required Date'] = dataframe['Required Date'].apply(parse_timestamp)

    #Apply currency format
    def currency(x):
    	return "${:0,.2f}".format(x)
    dataframe['Sub Total']= dataframe['Sub Total'].apply(currency)

    #Open spreadsheet and then workseet
    gc = pygsheets.authorize(service_file='client_secret.json')
    ss = gc.open('Unleashed API Invoices Master List')
    wks1 = ss.worksheet(0)

    #Get last row number to use when creating named range later on.
    index_end = 'L' + str(len(dataframe.index) + 2)

    # Update a cell (Cell, "Data")
    print("Exporting dataframe to Google Sheets...")
    wks1.cell('A1').set_text_format('bold', True).value = 'Sales Enquiry as of ' + str(starttime)
    wks1.set_dataframe(dataframe.fillna(''),(2,1), fit=True)
    wks1.delete_named_range('invoices')
    wks1.create_named_range('invoices','A2',index_end) #Note: update_named_ranges doesn't work for some reason.
    finishtime = datetime.now() - starttime
    print("Update Complete in " + str(finishtime))
