import time
import logging
import eons
from Applicator import Applicator

class RulesetApplicator(Applicator):

	def __init__(this, name="Ruleset Applicator"):
		super().__init__(name)

		this.ruleset = eons.util.DotDict({
			"phase": "http_request_firewall_custom",
		})

		this.ruleDataMap = {
			"action": "action",
			"enabled": True,
			"description": "description",
			"expression": "expression",
			"action_parameters": "action_parameters",
		}

	def transform_expression(this, expression):
		return expression.replace("'", '"')

	# Recursively transform action parameters.
	# Primarily, this is used in case there is an expression somewhere in the action parameters.
	def transform_action_parameters(this, action_parameters):
		if (isinstance(action_parameters) is dict or isinstance(action_parameters) is eons.util.DotDict):
			for key in action_parameters:
				action_parameters[key] = this.transform_action_parameters(action_parameters[key])
			return action_parameters
		
		if (isinstance(action_parameters) is list):
			return [this.transform_action_parameters(param) for param in action_parameters]
		
		if (isinstance(action_parameters) is str):
			return this.transform_expression(action_parameters)
		
		return action_parameters


	# Extract a value from a ruleObject.
	# The datum to extract must be a string, otherwise the datum itself is returned.
	# For example, if datum is "name", this will return something like ruleObject["name"] or ruleObject.name; but if the datum is False, this will return False.
	# This method will also apply any transform_...() rules you define, matching based on the datum name.
	# For example, if you have a transform_name() method, it will be called with the value of ruleObject["name"] or ruleObject.name.
	# See transform_expression() for an example.
	def GetRuleDatum(this, ruleObject, datum):
		if (isinstance(datum) is not str):
			return datum

		ret = None
		try:
			ret = getattr(ruleObject, datum)
		except Exception: # Exceptions thrown may not always be what you expect.
			try:
				ret = ruleObject[datum]
			except Exception:
				return None

		logging.debug(f"Extracted {datum}: {ret} ({type(ret)})")

		try:
			ret = getattr(this, f"transform_{datum}")(ret)
			logging.debug(f"Transformed {datum}: {ret} ({type(ret)})")
		except Exception:
			pass

		return ret

	# Extract all the data from a ruleObject.
	# This will return a dictionary of all the data in the ruleObject, with the keys being the datum names and the values being the extracted data.
	# This method will call GetRuleDatum() for each datum defined in this.ruleDataMap.
	def GetRuleData(this, ruleObject):
		ret = {}
		for datum in this.ruleDataMap.keys():
			value = this.GetRuleDatum(ruleObject, this.ruleDataMap[datum])
			if (value is not None):
				ret[datum] = value

		logging.debug(f"Extracted Rule Data: {ret}")

		return ret


	def CreateRulesetIfNotExists(this):
		rulesets = this.cf.rulesets.list(zone_id=this.domain_id).result  # REQUEST
		if (this.ruleset.phase not in [ruleset.phase for ruleset in rulesets]):
			logging.info(f"Creating {this.ruleset.phase} ruleset for {this.domain_name}")
			this.cf.rulesets.create(phase=this.ruleset.phase, zone_id=this.domain_id, kind='zone', name=this.settingId, rules=[]) # REQUEST
		
		time.sleep(1)


	def Apply(this):
		this.CreateRulesetIfNotExists()

		rules = this.cf.rulesets.phases.get(this.ruleset.phase, zone_id=this.domain_id).rules  # REQUEST

		ruleData = []

		if (rules is not None and (
			('wipe' not in this.setting) or
			('wipe' in this.setting and this.settingId not in this.setting['wipe'])
		)):
			for rule in rules:
				ruleData.append(this.GetRuleData(rule))

		for i, rule in enumerate(this.setting[this.settingId]):

			# rate limiting. keep us under 4 / sec.
			if (not i % 3):
				time.sleep(1)

			logging.debug(f"Applying {this.name} Rule Setting: {rule}")

			# check for the proper rule to update.
			ruleToUpdate = None
			for i, existing in enumerate(ruleData):
				if rule['description'] == existing['description']:
					ruleToUpdate = i
					break

			if (ruleToUpdate is not None):
				logging.info(f"Will update {rule['description']} in {this.domain_name}")
				
				ruleData[ruleToUpdate] = this.GetRuleData(rule)

			else:
				logging.info(f"Will create {rule['description']} in {this.domain_name}")

				ruleData.append(this.GetRuleData(rule))

		try:
			if (not this.dry_run):
				result = this.cf.rulesets.phases.update(this.ruleset.phase, zone_id=this.domain_id, rules=ruleData) #REQUEST
				logging.info(f"Result: {result}")

		except Exception as e:
			logging.error('API call failed (%d): %s\nData: %s' % (e, e, ruleData))
			if (this.errors_are_fatal):
				exit()
			else:
				this.domains_with_errors.append(this.domain)