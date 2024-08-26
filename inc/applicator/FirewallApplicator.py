import time
import logging
from RulesetApplicator import RulesetApplicator

class FirewallApplicator(RulesetApplicator):

	def __init__(this, name="Firewall Applicator"):
		super().__init__(name)

		this.settingId = "firewall_rules"
		this.ruleset.phase = "http_request_firewall_custom"
