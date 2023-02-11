import eons
import logging

class Applicator(eons.StandardFunctor):

	def __init__(this, name="Applicator"):
		super().__init__(name)

		this.functionSucceeded = True
		this.rollbackSucceeded = True
		
		this.requiredKWArgs.append("setting")
		this.requiredKWArgs.append("domain")
		this.requiredKWArgs.append("domain_id")
		this.requiredKWArgs.append("domain_name")
		this.requiredKWArgs.append("domains_with_errors")
		this.requiredKWArgs.append("cf")
		
		this.optionalKWArgs['only_apply_to'] = []
		this.optionalKWArgs['backup'] = True
		this.optionalKWArgs['backup_path'] = "bak"
		this.optionalKWArgs['dry_run'] = True
		this.optionalKWArgs['testing'] = False
		this.optionalKWArgs['errors_are_fatal'] = False
		
		this.argMapping.append("setting")
		this.argMapping.append("domain")
		this.argMapping.append("domain_id")
		this.argMapping.append("domain_name")
		this.argMapping.append("domains_with_errors")

		this.dns_allows_multiple_records = ['TXT', 'MX']

	def Function(this):
		return this.Apply()
	
	def Apply(this):
		pass