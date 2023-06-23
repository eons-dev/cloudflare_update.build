import os
import logging
import shutil
import re
import json
import time
import CloudFlare
import eons
from eot import EOT
from ebbs import Builder
from ebbs import OtherBuildError
from pathlib import Path

###################################################################
#					GENERAL INFORMATION
#
# Cloudflare API rate limit is 1200 requests per 5 minutes.
# This evaluates to 4 requests per second.
# The following code is catered to meet this requirement.
###################################################################

class cloudflare_update(Builder):
	# This was moved into builder json and is no longer required.
	# class Record:
	#	 def __init__(self, name, data, search_term, record_type='TXT'):
	#		 self.name = name
	#		 self.data = data
	#		 self.search_term = search_term
	#		 self.record_type = record_type

	def __init__(this, name="Cloudflare Update"):
		super().__init__(name)

		# We don't use the local filesystem
		this.clearBuildPath = False
		this.supportedProjectTypes = []

		this.requiredKWArgs.append("cf_email")
		this.requiredKWArgs.append("cf_token")  # global api key (TODO: can this work with other tokens?)

		this.optionalKWArgs['only_apply_to'] = []
		this.optionalKWArgs['backup'] = True
		this.optionalKWArgs['backup_path'] = "bak"
		this.optionalKWArgs['dry_run'] = True
		this.optionalKWArgs['testing'] = False
		this.optionalKWArgs['errors_are_fatal'] = False


    # Required Builder method. See that class for details.
	def Build(this):
		eons.SelfRegistering.RegisterAllClassesInDirectory(Path(this.executor.repo.store).joinpath("applicator").resolve())
		this.methods["DNSApplicator"] = eons.SelfRegistering("DNSApplicator")
		this.methods["PageRuleApplicator"] = eons.SelfRegistering("PageRuleApplicator")
		this.methods["FirewallApplicator"] = eons.SelfRegistering("FirewallApplicator")
		this.methods["CacheRuleApplicator"] = eons.SelfRegistering("CacheRuleApplicator")
		this.PopulateMethods()
		this.Validate()
		this.Authenticate()
		if (this.backup):
			this.Backup()
		this.Update()


	# Make sure we have what we need.
	# Raise errors for anything wrong or missing.
	# RETURN void.
	def Validate(this):
		pass


	# Create this.cf.
	def Authenticate(this):
		args = {
			#'email': this.cf_email,
			'token': this.cf_token,
			'raw': True
		}
		# if logging.DEBUG >= logging.root.level:
		#	 args['debug'] = True

		this.cf = CloudFlare.CloudFlare(**args)


	def GetDomainConfig(this, domain_name, domain_id):
		ret = {}
		try:
			params = {'name': f'_config.{domain_name}', 'match': 'all', 'type': 'TXT'}
			dns_records = this.cf.zones.dns_records.get(domain_id, params=params)['result']
			logging.debug(f"Config records: {dns_records}")

			config_contents = dns_records[0]['content']
			ret = json.loads(config_contents)
			if ('type' not in ret):
				raise Exception(f"Please specify the 'type' of {domain_name} in the _config record.")
		except Exception as e:
			logging.error(f"No valid config found for {domain_name}. Please ensure the domain has a _config record containing valid json. Error: {str(e)}")
			if (this.errors_are_fatal):
				raise Exception("Invalid _config")
		return ret


	def Set(this, varName, value, evaluateExpressions=False):
		super().Set(varName, value, evaluateExpressions)


	#TODO: Use eons.UserFunctor.EvaluateToType
	def EvaluateSetting(this, setting, domain_name, domain_config):
		if (isinstance(setting, dict)):
			ret = {}
			for key, value in setting.items():
				ret[key] = this.EvaluateSetting(value, domain_name, domain_config)
			return ret

		elif (isinstance(setting, list)):
			ret = []
			for value in setting:
				ret.append(this.EvaluateSetting(value, domain_name, domain_config))
			return ret

		else:
			evaluated_setting = eval(f"f\"{setting}\"")

			#Check original type and return the proper value.
			if (isinstance(setting, (bool, int, float)) and evaluated_setting == str(setting)):
				return setting

			#Check resulting type and return a casted value.
			#TODO: is there a better way than double cast + comparison?
			if (evaluated_setting.lower() == "false"):
				return False
			elif (evaluated_setting.lower() == "true"):
				return True

			try:
				if (str(float(evaluated_setting)) == evaluated_setting):
					return float(evaluated_setting)
			except:
				pass

			try:
				if (str(int(evaluated_setting)) == evaluated_setting):
					return int(evaluated_setting)
			except:
				pass

			#Type checks failed, string is appropriate.
			return evaluated_setting

			#We could allow @ to be "domain_name", as it is in cloudflare. However, this makes writing and talking about emails rather difficult.
			#
			#Make sure the domain name is properly substituted.
			# return evaluated_setting.replace('@', domain_name).replace(f'\\{domain_name}', '@')


	def Backup(this):
		backup_file = this.CreateFile(
			os.path.join(this.buildPath, this.backup_path, f"Cloudflare-bak_{EOT.GetStardate()}.txt"))

		page_number = 0
		while True:
			page_number += 1
			
			if (this.testing):
				raw_results = this.cf.zones.get(params={'per_page': 2, 'page': page_number})
			else:
				raw_results = this.cf.zones.get(params={'per_page': 20, 'page': page_number})
			
			domains = raw_results['result']

			for domain in domains:
				time.sleep(1)  # rate limiting

				domain_id = domain['id']
				domain_name = domain['name']
				logging.info(f"{domain_name} ({domain_id})")

				if (len(this.only_apply_to) and domain_name not in this.only_apply_to):
					logging.info(f"Skipping {domain_name}: not in {this.only_apply_to}")
					continue

				# DNS Records
				try:
					dns_records = this.cf.zones.dns_records.get(domain_id)['result']  # REQUEST

					backup_file.write(f"--- DNS RECORDS FOR {domain_name} ---\n")
					for r in dns_records:
						logging.info(f"Got record: {r}")
						backup_file.write(f"{domain_name} ({domain_id}): {r}\n")

				except CloudFlare.exceptions.CloudFlareAPIError as e:
					logging.error('/zones/dns_records.get %d %s - api call failed' % (e, e))

				# Page Rules
				try:
					page_rules = this.cf.zones.pagerules.get(domain_id)['result']  # REQUEST

					backup_file.write(f"--- PAGE RULES FOR {domain_name} ---\n")
					for r in page_rules:
						logging.info(f"Got page rule: {r}")
						backup_file.write(f"{domain_name} ({domain_id}): {r}\n")

				except CloudFlare.exceptions.CloudFlareAPIError as e:
					logging.error('/zones/pagerules.get %d %s - api call failed' % (e, e))

				# Firewall Rules
				try:
					fw_rules = this.cf.zones.firewall.rules.get(domain_id)['result']  # REQUEST

					backup_file.write(f"--- FIREWALL RULES FOR {domain_name} ---\n")
					for r in fw_rules:
						logging.info(f"Got firewall rule: {r}")
						backup_file.write(f"{domain_name} ({domain_id}): {r}\n")

				except CloudFlare.exceptions.CloudFlareAPIError as e:
					logging.error('/zones/firewall/rules.get %d %s - api call failed' % (e, e))

				logging.info(f"---- COMPLETED {domain_name} ----")

				if (this.testing):
					break

			total_pages = raw_results['result_info']['total_pages']
			if (page_number == total_pages):
				break

		backup_file.close()
		

	def Update(this):
		page_number = 0
		while True:
			page_number += 1
			
			if (this.testing):
				raw_results = this.cf.zones.get(params={'per_page': 2, 'page': page_number})
			else:
				raw_results = this.cf.zones.get(params={'per_page': 20, 'page': page_number})
			
			domains = raw_results['result']

			domains_with_errors = []

			for domain in domains:
				time.sleep(1)  # rate limiting

				domain_id = domain['id']
				domain_name = domain['name']
				domain_config = this.GetDomainConfig(domain_name, domain_id)  # REQUEST
				logging.info(f"{domain_name} ({domain_id}): {domain_config}")

				if (len(this.only_apply_to) and domain_name not in this.only_apply_to):
					logging.info(f"Skipping {domain_name}: not in {this.only_apply_to}")
					continue

				for setting in this.config['domains']:
					if ("match" not in setting):
						continue
					setting_can_be_applied = True
					logging.debug(f"Trying to match with {setting['match']}")
					for key, value in setting['match'].items():
						if (key not in domain_config or domain_config[key] != value):
							setting_can_be_applied = False
							break
					if (not setting_can_be_applied):
						continue

					# Apply dynamic configuration
					setting = this.EvaluateSetting(setting, domain_name, domain_config)
					logging.debug(f"Will apply {setting}")

					for wipe in setting['wipe']:
						if (wipe == 'page_rules'):
							params = {'match': 'all'}
							page_rules = this.cf.zones.pagerules.get(domain_id, params=params)['result']
							for i, pgr in enumerate(page_rules):
								logging.debug(f"Will delete page rule {pgr}")
								if (not this.dry_run):
									this.cf.zones.pagerules.delete(domain_id, pgr['id'])
								if (not i % 3):
									time.sleep(1)  # rate limiting. keep us under 4 / sec.
						elif (wipe == 'firewall_rules'):
							firewall_rules = this.cf.zones.firewall.rules.get(domain_id)['result']
							for i, fwr in enumerate(firewall_rules):
								logging.debug(f"Will delete firewall rule {fwr}")
								if (not this.dry_run):
									this.cf.zones.firewall.rules.delete(domain_id, fwr['id'])

								# rate limiting. keep us under 4 / sec.
								if (not i % 3):
									time.sleep(1)

							filters = this.cf.zones.filters.get(domain_id)['result']
							for i, flt in enumerate(filters):
								logging.debug(f"Will delete filter {flt}")
								if (not this.dry_run):
									this.cf.zones.filters.delete(domain_id, flt['id'])

								# rate limiting. keep us under 4 / sec.
								if (not i % 3):
									time.sleep(1)
					
					this.DNSApplicator(setting, domain, domain_id, domain_name, domains_with_errors, precursor = this, executor=this.executor)
					this.PageRuleApplicator(setting, domain, domain_id, domain_name, domains_with_errors, precursor = this, executor=this.executor)
					this.FirewallApplicator(setting, domain, domain_id, domain_name, domains_with_errors, precursor = this, executor=this.executor)
					this.CacheRuleApplicator(setting, domain, domain_id, domain_name, domains_with_errors, precursor = this, executor=this.executor)

					if (this.testing):
						break

				logging.info(f"---- done with {domain_name} ----")

			if (this.testing):
				break

			total_pages = raw_results['result_info']['total_pages']
			if (page_number == total_pages):
				break

		logging.info("Complete!")
		if (len(domains_with_errors)):
			logging.error(f"The following domains had errors: {domains_with_errors}")
