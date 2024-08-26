import time
import logging
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
		try:
			currentRules = this.cf.rulesets.phases.get('http_request_cache_settings', zone_id=this.domain_id)
		except Exception as e:
			logging.error(str(e))
			return

		try:
			[cache_rules['rules'].append(exist) for exist in currentRules.rules if exist.description not in [rule['description'] for rule in cache_rules['rules']]]
		except Exception as e:
			logging.warning(str(e))

		try:
			this.cf.rulesets.phases.update('http_request_cache_settings', zone_id=this.domain_id, **cache_rules)
		except Exception as e:
			logging.error(str(e))
			return