import time
import logging
import CloudFlare
from Applicator import Applicator

class CacheRuleApplicator(Applicator):

	def __init__(this, name="CacheRuleApplicator"):
		super().__init__(name)
				
	def Apply(this):
		
		if ('cache_rules' not in this.setting):
			return
		time.sleep(1)  # rate limiting
			
		cache_rules = {
			'rules': this.setting['cache_rules']
		}

		for rule in cache_rules['rules']:
			if 'expression' not in rule:
				continue
			rule['expression'] = rule['expression'].replace("'",'"')
		this.cf.zones.rulesets.phases.http_request_cache_settings.entrypoint.put(this.domain_id, data=cache_rules)