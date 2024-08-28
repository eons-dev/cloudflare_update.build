import os
import logging
import shutil
import re
import json
import time
import cloudflare
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
		this.optionalKWArgs['purge_cache'] = False
		this.optionalKWArgs['backup'] = True
		this.optionalKWArgs['backup_path'] = "bak"
		this.optionalKWArgs['dry_run'] = True
		this.optionalKWArgs['testing'] = False
		this.optionalKWArgs['errors_are_fatal'] = False


	@eons.method(impl="External")
	def RedirectApplicator(this):
		pass

	@eons.method(impl="External")
	def CacheRuleApplicator(this):
		pass

	@eons.method(impl="External")
	def DNSApplicator(this):
		pass

	@eons.method(impl="External")
	def FirewallApplicator(this):
		pass

	@eons.method(impl="External")
	def PageRuleApplicator(this):
		pass

    # Required Builder method. See that class for details.
	def Build(this):

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
		this.cf = cloudflare.Cloudflare(api_email=this.cf_email, api_key=this.cf_token)


	def GetDomainConfig(this, domain_name, domain_id):
		ret = {}
		try:
			dns_records = this.cf.dns.records.list(zone_id=domain_id, type='TXT', name=f'_config.{domain_name}')
			logging.debug(f"Config records: {dns_records}")

			config_contents = None
			for r in dns_records:
				config_contents = r.content
				break

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
			os.path.join(this.buildPath, this.backup_path, f"Cloudflare-bak_{EOT.GetStardate()}.txt")
		)

		for zone in this.cf.zones.list():
			time.sleep(1)  # rate limiting
			
			domain_id = zone.id
			domain_name = zone.name
			logging.info(f"{domain_name} ({domain_id})")

			if (len(this.only_apply_to) and domain_name not in this.only_apply_to):
				logging.info(f"Skipping {domain_name}: not in {this.only_apply_to}")
				continue

			# DNS Records
			try:
				dns_records = this.cf.dns.records.list(zone_id=domain_id)  # REQUEST

				backup_file.write(f"--- DNS RECORDS FOR {domain_name} ---\n")
				for r in dns_records:
					logging.info(f"Got record: {r}")
					backup_file.write(f"{domain_name} ({domain_id}): {r}\n")

			except Exception as e:
				logging.error('/zones/dns_records.get %d %s - api call failed' % (e, e))

			# Page Rules
			try:
				page_rules = this.cf.pagerules.list(zone_id=domain_id)  # REQUEST

				backup_file.write(f"--- PAGE RULES FOR {domain_name} ---\n")
				for r in page_rules:
					logging.info(f"Got page rule: {r}")
					backup_file.write(f"{domain_name} ({domain_id}): {r}\n")

			except Exception as e:
				logging.error('/zones/pagerules.get %d %s - api call failed' % (e, e))

			# Firewall Rules
			try:
				fw_rules = this.cf.rulesets.phases.get('http_request_firewall_custom ', zone_id=domain_id)  # REQUEST

				backup_file.write(f"--- FIREWALL RULES FOR {domain_name} ---\n")
				for r in fw_rules.rules:
					logging.info(f"Got firewall rule: {r}")
					backup_file.write(f"{domain_name} ({domain_id}): {r}\n")

			except Exception as e:
				logging.error('/zones/firewall/rules.get %d %s - api call failed' % (e, e))

			logging.info(f"---- COMPLETED {domain_name} ----")

			if (this.testing):
				break

		backup_file.close()
		

	def Update(this):
		domains_with_errors = []

		for zone in this.cf.zones.list():
			time.sleep(1)  # rate limiting

			domain_id = zone.id
			domain_name = zone.name
			domain_config = this.GetDomainConfig(domain_name, domain_id)  # REQUEST
			logging.info(f"{domain_name} ({domain_id}): {domain_config}")

			if (len(this.only_apply_to) and domain_name not in this.only_apply_to):
				logging.info(f"Skipping {domain_name}: not in {this.only_apply_to}")
				continue

			if (this.purge_cache):
				logging.info(f"Purging cache for {domain_name}")
				this.cf.cache.purge(domain_id, purge_everything=True) # REQUEST

			for setting in this.config['domains']:
				if ("match" not in setting):
					continue
				setting_can_be_applied = True
				logging.debug(f"Trying to match with {setting['match']}")
				for key, value in setting['match'].items():
					matched = False

					invert = False
					if (key.startswith("!")):
						key = key[1:]
						invert = True

					if (key not in domain_config):
						# Fatal
						logging.error(f"Match key not found in config: {key}, config: {domain_config}")
						setting_can_be_applied = False
						break

					configValue = domain_config[key]

					if (isinstance(value, list)):
						if (isinstance(configValue, list)): # ALL of value iff both are lists
							matched = True
							for v in value:
								if (v not in configValue):
									matched = False
									break
						elif (isinstance(configValue, str)): # ANY iff one is a string and the other is a list
							matched = (configValue in value)
						else:
							# Fatal
							logging.error(f"Invalid match value: {value} ({type(value)})")
							setting_can_be_applied = False
							break
					elif (isinstance(value, str)):
						if (isinstance(configValue, list)): # ANY iff one is a string and the other is a list
							matched = (value in configValue)
						elif (isinstance(configValue, str)): # == iff both are strings
							matched = (value == configValue)
						else:
							# Fatal
							logging.error(f"Invalid match config: {configValue} ({type(configValue)})")
							setting_can_be_applied = False
							break
					else:
						# Fatal
						logging.error(f"Invalid match value: {value} ({type(value)})")
						setting_can_be_applied = False
						break

					if (invert):
						matched = not matched

					if (not matched):
						setting_can_be_applied = False
						break

				if (not setting_can_be_applied):
					continue

				# Apply dynamic configuration
				setting = this.EvaluateSetting(setting, domain_name, domain_config)
				logging.debug(f"Will apply {setting}")

				if ('wipe' in setting):
					for wipe in setting['wipe']:
						if (wipe == 'page_rules'):
							page_rules = this.cf.pagerules.list(zone_id=domain_id)
							for i, pgr in enumerate(page_rules):
								logging.debug(f"Will delete page rule {pgr}")
								if (not this.dry_run):
									this.cf.pagerules.delete(pgr.id, zone_id=domain_id)
								if (not i % 3):
									time.sleep(1)  # rate limiting. keep us under 4 / sec.

				this.DNSApplicator(setting, zone, domain_id, domain_name, domains_with_errors, precursor = this)
				this.PageRuleApplicator(setting, zone, domain_id, domain_name, domains_with_errors, precursor = this)
				this.FirewallApplicator(setting, zone, domain_id, domain_name, domains_with_errors, precursor = this)
				this.CacheRuleApplicator(setting, zone, domain_id, domain_name, domains_with_errors, precursor = this)
				this.RedirectApplicator(setting, zone, domain_id, domain_name, domains_with_errors, precursor = this)

				if (this.testing):
					break

			logging.info(f"---- done with {domain_name} ----")

		logging.info("Complete!")
		if (len(domains_with_errors)):
			logging.error(f"The following domains had errors: {domains_with_errors}")
