import time
import logging
import eons
from Applicator import Applicator

class RulesetApplicator(Applicator):

	def __init__(this, name="Ruleset Applicator"):
		super().__init__(name)

		this.ruleset = eons.DotDict({
			"phase": "http_request_firewall_custom",
		})


	def Apply(this):
		rules = this.cf.rulesets.phases.get(this.ruleset.phase, zone_id=this.domain_id).rules  # REQUEST

		ruleData = []

		for rule in rules:
			ruleData.append({
				"action": rule.action,
				"priority": rule.priority,
				"paused": False,
				"description": rule.description,
				"expression": rule.expression,
			})

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
					
					ruleData[ruleToUpdate] = {
						"action": rule['action'],
						"priority": rule['priority'],
						"paused": False,
						"description": rule['name'],
						"expression": rule['expression'].replace("'", '"'),
					}

				else:
					logging.info(f"Will create {rule['name']} in {this.domain_name}")

					ruleData.append({
						"action": rule['action'],
						"priority": rule['priority'],
						"paused": False,
						"description": rule['name'],
						"expression": rule['expression'].replace("'", '"'),
					})

		try:
			if (not this.dry_run):
				result = this.cf.rulesets.phases.update(this.ruleset.phases, zone_id=this.domain_id, rules=ruleData) #REQUEST
				logging.info(f"Result: {result}")

		except Exception as e:
			logging.error('API call failed (%d): %s\nData: %s' % (e, e, ruleData))
			if (this.errors_are_fatal):
				exit()
			else:
				this.domains_with_errors.append(this.domain)