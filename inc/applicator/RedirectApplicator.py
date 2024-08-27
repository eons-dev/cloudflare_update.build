import time
import logging
import eons
from RulesetApplicator import RulesetApplicator

class RedirectApplicator(RulesetApplicator):

	def __init__(this, name="Redirect Applicator"):
		super().__init__(name)

		this.settingId = "redirects"
		this.ruleset.phase = "http_request_dynamic_redirect"