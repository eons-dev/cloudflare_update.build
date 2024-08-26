import time
import logging
from Applicator import Applicator

class DNSApplicator(Applicator):

	def __init__(this, name="DNS Applicator"):
		super().__init__(name)

		this.settingId = "dns"
				
	def Apply(this):

		for i, dns in enumerate(this.setting['dns']):

			# rate limiting. keep us under 4 / sec.
			# if (not i % 2): #at limit (3 possible requests per iteration).
			time.sleep(1)

			logging.debug(f"Applying DNS this.setting: {dns}")

			if (('type' not in dns) or ('domain' not in dns) or ('content' not in dns)):
				logging.error(f"Invalid dns entry: {dns}")
				continue

			params = {'name': dns['domain'], 'match': 'all'}
			if (dns['type'] in this.dns_allows_multiple_records):
				params['type'] = dns['type']
			dns_records = this.cf.dns.records.list(zone_id=this.domain_id, **params)  # REQUEST
			existing_record = None

			#Check for the proper record to update.
			#This logic is complex in order to handle cases where you want to replace an A record with a CNAME or some other record type transmutation.
			if (len(dns_records.result)):
				if (dns['type'] in this.dns_allows_multiple_records and 'update_term' in dns):
					for existing in dns_records:
						if (dns['domain'] == existing.name and dns['update_term'] in existing.content):
							
							if (existing_record is not None): # duplicate record found
								logging.debug(f"Deleting duplicate record with: {existing_record.content}")
								time.sleep(1) #Sleep just in case
								result = this.cf.dns.records.delete(existing.id, zone_id=this.domain_id) #possible additional request: Delete
							else:
								existing_record = existing
								logging.debug(f"Will update existing {existing_record.type} record containing: {existing_record.content}")

					if (existing_record is None):
						logging.debug(f"Could not find existing record matching {dns['domain']} and update_term {dns['update_term']}")
				else:
					single_instance_dns_records = [d for d in dns_records if d.type not in this.dns_allows_multiple_records]
					if (len(single_instance_dns_records) == 1):
						existing_record = None
						for r in dns_records:
							existing_record = r
							break
						logging.debug(f"Will update existing {existing_record.type} record")
					else:
						for existing in single_instance_dns_records:
							if (dns['domain'] == existing.name and dns['type'] == existing.type):
								existing_record = existing
								logging.debug(f"Multiple matches found for {dns['domain']}. Using existing {dns['type']} record.")
								break
					if (existing_record is None):
						logging.warn(f"Could not find appropriate existing record for {dns['domain']}. Candidates were: {single_instance_dns_records}")
			else:
				logging.debug(f"No matching records found on {this.domain_name} with params: {params}")

			record_data = {
				'name': dns['domain'],
				'type': dns['type'],
				'content': dns['content']
			}
			if ((dns['type'] not in this.dns_allows_multiple_records) and (dns['content'].endswith(this.domain_name))):
				record_data['proxied'] = True

			try:
				result = {}

				if (existing_record is not None):
					logging.info(f"Will delete existing record: {existing_record}")
					if (not this.dry_run):
						result = this.cf.dns.records.delete(existing_record.id, zone_id=this.domain_id) #POSSIBLE REQUEST: Delete
						logging.info(f"Result: {result}")

				logging.info(f"Will create {dns['type']} record {dns['domain']} in {this.domain_name}")
				if (not this.dry_run):
					result = this.cf.dns.records.create(zone_id=this.domain_id, **record_data)  # REQUEST: Create
					logging.info(f"Result: {result}")

			except Exception as e:
				logging.error('API call failed (%d): %s\nData: %s' % (e, e, record_data))
				if (this.errors_are_fatal):
					exit()
				else:
					this.domains_with_errors.append(this.domain)