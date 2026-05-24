#!/usr/bin/env python3

# Script to convert Apple Health data to Fitbit CSV data

import os.path
import xml.etree.ElementTree as ET

from datetime import datetime

NS = {'cda': 'urn:hl7-org:v3'}

if not os.path.exists('export_cda.xml'):
  print("Error: export_cda.xml not found.")
  exit(1)

if not os.path.exists('export.xml'):
  print("Error: export.xml not found.")
  exit(1)

height_cm_input = input("What is your height in cm? ")
try:
	height_cm = int(height_cm_input)
	height_m = float(height_cm) / 100.0
except:
	print("Unable to parse input.")
	exit(1)

print("OK. Parsing files...")

try:
  export_cda = ET.parse('export_cda.xml')
except ET.ParseError as error:
	print("Unable to parse 'export_cda.xml', it might be invalid XML.")
	print("Try to fix 'export_cda.xml' by running the included 'fix_invalid_export_cda_xml' script.")
	print("Exiting")
	exit(1)

try:
	export = ET.parse('export.xml')
except ET.ParseError as error:
	print("Failed to parse 'export.xml'.")
	print("Exiting")
	exit(1)


export_cda_root = export_cda.getroot()
export_root = export.getroot()

# Go through export_cda.xml to get all weight values

weight_dict = {}
weight_time_dict = {}

def parse_apple_date(value):
	return datetime.strptime(value, '%Y-%m-%d %H:%M:%S %z')

def parse_cda_date(value):
	return datetime.strptime(value, '%Y%m%d%H%M%S%z')

def date_string_from_datetime(value):
	return value.strftime('%d-%m-%Y')

def add_weight(date_time, value, unit='kg'):
	date_string = date_string_from_datetime(date_time)
	weight_kg = float(value)
	if unit in ['lb', 'lbs', '[lb_av]']:
		weight_kg = weight_kg * 0.45359237

	if date_string not in weight_time_dict or date_time >= weight_time_dict[date_string]:
		weight_time_dict[date_string] = date_time
		weight_dict[date_string] = round(weight_kg, 3)

for observation in export_cda_root.findall('.//cda:observation', NS):
	code = observation.find('cda:code', NS)
	if code is None or code.get('code') != "3141-9":
		continue

	value = observation.find('cda:value', NS)
	effective_time = observation.find('cda:effectiveTime', NS)
	if value is None or effective_time is None:
		continue

	low_time = effective_time.find('cda:low', NS)
	time_value = None
	if low_time is not None and low_time.get('value') is not None:
		time_value = parse_cda_date(low_time.get('value'))
	elif effective_time.get('value') is not None:
		time_value = parse_cda_date(effective_time.get('value'))

	if time_value is not None and value.get('value') is not None:
		add_weight(time_value, value.get('value'), value.get('unit', 'kg'))

# Go through export.xml to get all activities, steps, distance, floors climbed

steps_dict = {}
distance_dict = {}
floors_dict = {} 
active_calories_dict = {}
basal_calories_dict = {}
lightly_active_minutes_dict = {}
fairly_active_minutes_dict = {}
very_active_minutes_dict = {}

# Helper function to parse int
def parse_to_int(s):
    try:
        return int(s)
    except ValueError:
        return int(float(s))

def add_to_dict(data_dict, date_key, value):
	if date_key in data_dict:
		data_dict[date_key] = data_dict[date_key] + value
	else:
		data_dict[date_key] = value

def convert_energy_to_kcal(value, unit):
	value = float(value)
	if unit == 'kJ':
		return value * 0.239005736
	return value

for record in export_root.findall('Record'):
	start_date = parse_apple_date(record.get('startDate'))
	date_string = date_string_from_datetime(start_date)
	value = record.get('value')
	record_type = record.get('type')

	# Aggregate the data by calculating the sum for each date
	if(record_type == "HKQuantityTypeIdentifierBodyMass"):
		add_weight(start_date, value, record.get('unit', 'kg'))

	if(record_type == "HKQuantityTypeIdentifierStepCount"):
		add_to_dict(steps_dict, date_string, parse_to_int(value))

	if(record_type in ["HKQuantityTypeIdentifierDistanceWalkingRunning", "HKQuantityTypeIdentifierDistanceCycling"]):
		add_to_dict(distance_dict, date_string, float(value))

	if(record_type == "HKQuantityTypeIdentifierFlightsClimbed"):
		add_to_dict(floors_dict, date_string, parse_to_int(value))

	if(record_type == "HKQuantityTypeIdentifierActiveEnergyBurned"):
		add_to_dict(active_calories_dict, date_string, convert_energy_to_kcal(value, record.get('unit')))

	if(record_type == "HKQuantityTypeIdentifierBasalEnergyBurned"):
		add_to_dict(basal_calories_dict, date_string, convert_energy_to_kcal(value, record.get('unit')))

for workout in export_root.findall('Workout'):
	start_date = parse_apple_date(workout.get('startDate'))
	date_string = date_string_from_datetime(start_date)
	duration = round(float(workout.get('duration', '0')))
	activity_type = workout.get('workoutActivityType')

	if activity_type == "HKWorkoutActivityTypeWalking":
		add_to_dict(lightly_active_minutes_dict, date_string, duration)
	elif activity_type in ["HKWorkoutActivityTypeTraditionalStrengthTraining", "HKWorkoutActivityTypeOther"]:
		add_to_dict(fairly_active_minutes_dict, date_string, duration)
	else:
		add_to_dict(very_active_minutes_dict, date_string, duration)

# Find out which years we need to print
# All dict keys are formated with "time_value.strftime('%d-%m-%Y')"
years = []

for date_key in weight_dict:
	tmp_year = datetime.strptime(date_key, '%d-%m-%Y').strftime('%Y')
	if tmp_year not in years:
		print("Found weight data for " + tmp_year)
		years.append(tmp_year)

for date_key in steps_dict:
	tmp_year = datetime.strptime(date_key, '%d-%m-%Y').strftime('%Y')
	if tmp_year not in years:
		print("Found step data for " + tmp_year)
		years.append(tmp_year)

activity_dates = set(steps_dict) | set(distance_dict) | set(floors_dict) | set(active_calories_dict) | set(basal_calories_dict) | set(lightly_active_minutes_dict) | set(fairly_active_minutes_dict) | set(very_active_minutes_dict)

for date_key in activity_dates:
	tmp_year = datetime.strptime(date_key, '%d-%m-%Y').strftime('%Y')
	if tmp_year not in years:
		print("Found activity data for " + tmp_year)
		years.append(tmp_year)

print("Now generating FitBit CSV files for the following years: " + ', '.join(years))

for file_year in years:
	filename = "fitbit_" + file_year + ".csv"
	print("Writing " + filename + "...")
	with open(filename, 'w') as output_file:

	  # Print weight

		# Header
		output_file.write("Body\n")
		output_file.write("Date,Weight,BMI,Fat\n")

		# Data
		for date_key in sorted(weight_dict, key=lambda date: datetime.strptime(date, '%d-%m-%Y')):
			dict_year = datetime.strptime(date_key, '%d-%m-%Y').strftime('%Y')
			if(dict_year == file_year):
				value = weight_dict[date_key]
				bmi = round(float(value) / (height_m * height_m),2)
				output_file.write("\"%s\",\"%s\",\"%s\",\"0\"\n" % (date_key, value, bmi))

		# Print activities

		# Header
		output_file.write("\n")
		output_file.write("Activities\n")
		output_file.write("Date,Calories Burned,Steps,Distance,Floors,Minutes Sedentary,Minutes Lightly Active,Minutes Fairly Active,Minutes Very Active,Activity Calories\n")

		# Data
		for date_key in sorted(activity_dates, key=lambda date: datetime.strptime(date, '%d-%m-%Y')):
			dict_year = datetime.strptime(date_key, '%d-%m-%Y').strftime('%Y')
			if(dict_year == file_year):
				output = "\""
				output += date_key
				output += "\",\""
				output += str(round(basal_calories_dict.get(date_key, 0) + active_calories_dict.get(date_key, 0)))
				output += "\",\""

				if date_key in steps_dict:
					output += str("{:,}".format(steps_dict[date_key]))
				else:
					output += "0"
			    
				output += "\",\""

				if date_key in distance_dict:
					output += str(round(distance_dict[date_key],2))
				else:
					output += "0"

				output += "\",\""

				if date_key in floors_dict:
					output += str(floors_dict[date_key])
				else:
					output += "0"

				output += "\",\"0\",\""
				output += str(lightly_active_minutes_dict.get(date_key, 0))
				output += "\",\""
				output += str(fairly_active_minutes_dict.get(date_key, 0))
				output += "\",\""
				output += str(very_active_minutes_dict.get(date_key, 0))
				output += "\",\""
				output += str(round(active_calories_dict.get(date_key, 0)))
				output += "\"\n"

				output_file.write(output)

print("Done.")
