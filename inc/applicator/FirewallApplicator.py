import time
import logging
from Applicator import Applicator

class FirewallApplicator(Applicator):

	def __init__(this, name="FirewallApplicator"):
		super().__init__(name)
				
	def Apply(this):
		if ('firewall_rules' in this.setting):
			time.sleep(1)  # rate limiting

			#Unlike DNS, this result does not depend on params and can be cached.
			firewall_rules = this.cf.firewall.rules.list(this.domain_id)  # REQUEST

			for i, fwr in enumerate(this.setting['firewall_rules']):

				# rate limiting. keep us under 4 / sec.
				if (not i % 3):
					time.sleep(1)

				logging.debug(f"Applying Firewall Rule Setting: {fwr}")

				# TODO: input checking.

				# check for the proper rule to update.
				rule_to_update = None
				if (len(firewall_rules.result)):
					for existing in firewall_rules:	
						if fwr['name'] == existing.filter.description:
							rule_to_update = existing
							break

				rule_data = [{
					"action": fwr['action'],
					"priority": fwr['priority'],
					"paused": False,
					"description": fwr['name'],
					"filter": {
						"expression": fwr['expression'].replace("'", '"'),
						"paused": False,
						"description": fwr['name'],
					}
				}]

				try:
					result = {}

					if (rule_to_update is not None):
						raise Exception("Firewall rules cannot be updated at this time. They must be wiped and recreated.")
						# r_id = rule_to_update['id']
						#
						# logging.info(f"Will update {fwr['name']} in {domain_name}")
						# if (not this.dry_run):
						#	 result = this.cf.zones.firewall.rules.put(domain_id, r_id, data=rule_data) #REQUEST: Update
						#	 logging.info(f"Result: {result}")

					else:
						logging.info(f"No matching firewall rule found for {fwr['name']}")

						logging.info(f"Will create {fwr['name']} in {this.domain_name}")
						if (not this.dry_run):
							result = this.cf.firewall.rules.post(this.domain_id, data=rule_data) #REQUEST: Create
							logging.info(f"Result: {result}")

				except Exception as e:
					logging.error('API call failed (%d): %s\nData: %s' % (e, e, rule_data))
					if (this.errors_are_fatal):
						exit()
					else:
						this.domains_with_errors.append(this.domain)