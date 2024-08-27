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
			"priority": "priority",
			"paused": False,
			"description": "name",
			"expression": "expression",
		}

	def transform_expression(this, expression):
		return expression.replace("'", '"')

	# Extract a value from a ruleObject.
	# The datum to extract must be a string, otherwise the datum itself is returned.
	# For example, if datum is "name", this will return something like ruleObject["name"] or ruleObject.name; but if the datum is False, this will return False.
	# This method will also apply any transform_...() rules you define, matching based on the datum name.
	# For example, if you have a transform_name() method, it will be called with the value of ruleObject["name"] or ruleObject.name.
	# See transform_expression() for an example.
	def GetRuleDatum(this, ruleObject, datum):
		if (not datum is str):
			return datum

		ret = None
		try:
			ret = ruleObject[datum]
		except KeyError:
			try:
				ret = getattr(ruleObject, datum)
			except AttributeError:
				return None

		try:
			ret = getattr(this, f"transform_{datum}")(ret)
		except AttributeError:
			pass

		return ret

	# Extract all the data from a ruleObject.
	# This will return a dictionary of all the data in the ruleObject, with the keys being the datum names and the values being the extracted data.
	# This method will call GetRuleDatum() for each datum defined in this.ruleDataMap.
	def GetRuleData(this, ruleObject):
		ret = {}
		for datum in this.ruleDataMap.keys():
			ret[datum] = this.GetRuleDatum(ruleObject, this.ruleDataMap[datum])
		return ret


	def Apply(this):
		rules = this.cf.rulesets.phases.get(this.ruleset.phase, zone_id=this.domain_id).rules  # REQUEST

		ruleData = []

		if (rules is not None):
			for rule in rules:
				ruleData.append(this.GetRuleData(rule))

		for i, rule in enumerate(this.setting[this.settingId]):

			# rate limiting. keep us under 4 / sec.
			if (not i % 3):
				time.sleep(1)

			logging.debug(f"Applying {this.name} Rule Setting: {rule}")

			# TODO: input checking.

			# check for the proper rule to update.
			ruleToUpdate = None
			for i, existing in enumerate(ruleData):
				if rule['name'] == existing['description']:
					ruleToUpdate = i
					break

				if (ruleToUpdate is not None):
					logging.info(f"Will update {rule['name']} in {domain_name}")
					
					ruleData[ruleToUpdate] = this.GetRuleData(rule)

				else:
					logging.info(f"Will create {rule['name']} in {this.domain_name}")

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