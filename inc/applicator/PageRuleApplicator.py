import time
import logging
from Applicator import Applicator

class PageRuleApplicator(Applicator):

	def __init__(this, name="PageRuleApplicator"):
		super().__init__(name)
				
	def Apply(this):

		if ('page_rules' in this.setting):

			time.sleep(1)  # rate limiting

			#Unlike DNS, this result does not depend on params and can be cached.
			page_rules = this.cf.pagerules.list(this.domain_id)  # REQUEST

			for i, pgr in enumerate(this.setting['page_rules']):

				# rate limiting. keep us under 4 / sec.
				if (not i % 3):
					time.sleep(1)

				logging.debug(f"Applying Page Rule Setting: {pgr}")

				# TODO: input checking.

				# check for the proper rule to update.
				rule_to_update = None
				if (len(page_rules)):
					for existing in page_rules:
						if pgr['url'] in [target['constraint']['value'] for target in existing.targets]:
							rule_to_update = existing
							break

				targets = [{"target": "url", "constraint": {"operator": "matches", "value": pgr['url']}}]
				rule_data = {"status": "active", "priority": 1, "actions": pgr['actions'], "targets": targets}

				try:
					result = {}

					if (rule_to_update is not None):
						r_id = rule_to_update.id

						logging.info(f"Will update {pgr['url']} in {this.domain_name}")
						if (not this.dry_run):
							result = this.cf.zones.pagerules.put(this.domain_id, r_id, data=rule_data) # REQUEST: Update
							logging.info(f"Result: {result}")

					else:
						logging.info(f"No matching page rule found for {pgr['url']}")

						logging.info(f"Will create {pgr['url']} in {this.domain_name}")
						if (not this.dry_run):
							result = this.cf.zones.pagerules.post(this.domain_id, data=rule_data) # REQUEST: Create
							logging.info(f"Result: {result}")

				except Exception as e:
					logging.error('API call failed (%d): %s\nData: %s' % (e, e, rule_data))
					if (this.errors_are_fatal):
						exit()
					else:
						this.domains_with_errors.append(this.domain)