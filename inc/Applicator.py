import eons
import time
import logging

class Applicator(eons.StandardFunctor):

	def __init__(this, name="Applicator"):
		super().__init__(name)

		this.functionSucceeded = True
		this.rollbackSucceeded = True

		this.arg.kw.required.append("setting")
		this.arg.kw.required.append("domain")
		this.arg.kw.required.append("domain_id")
		this.arg.kw.required.append("domain_name")
		this.arg.kw.required.append("domains_with_errors")
		this.arg.kw.required.append("cf")

		this.arg.kw.optional['only_apply_to'] = []
		this.arg.kw.optional['backup'] = True
		this.arg.kw.optional['backup_path'] = "bak"
		this.arg.kw.optional['dry_run'] = True
		this.arg.kw.optional['testing'] = False
		this.arg.kw.optional['errors_are_fatal'] = False

		this.arg.mapping.append("setting")
		this.arg.mapping.append("domain")
		this.arg.mapping.append("domain_id")
		this.arg.mapping.append("domain_name")
		this.arg.mapping.append("domains_with_errors")

		this.dns_allows_multiple_records = ['TXT', 'MX']

		this.settingId = None

	def Function(this):
		if (this.settingId in this.setting):
			time.sleep(1)  # rate limiting
			return this.Apply()
		return None

	def Apply(this):
		pass