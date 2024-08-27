import time
import logging
import eons
from RulesetApplicator import RulesetApplicator

class CacheRuleApplicator(RulesetApplicator):

	def __init__(this, name="CacheRule Applicator"):
		super().__init__(name)

		this.settingId = "cache_rules"
		this.ruleset.phase = "http_request_cache_settings"