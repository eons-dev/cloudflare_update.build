import os
import logging
import shutil
import re
import json
import time
import CloudFlare
from eot import EOT
from ebbs import Builder
from ebbs import OtherBuildError


###################################################################
#                    GENERAL INFORMATION
#
# Cloudflare API rate limit is 1200 requests per 5 minutes.
# This evaluates to 4 requests per second.
# The following code is catered to meet this requirement.
###################################################################

class cloudflare_update(Builder):
    # This was moved into builder json and is no longer required.
    # class Record:
    #     def __init__(self, name, data, search_term, record_type='TXT'):
    #         self.name = name
    #         self.data = data
    #         self.search_term = search_term
    #         self.record_type = record_type

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
        this.optionalKWArgs['errors_are_fatal'] = False

        this.dns_allows_multiple_records = ['TXT', 'MX']

    # Required Builder method. See that class for details.
    def Build(this):
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
            'email': this.cf_email,
            'token': this.cf_token,
            'raw': True
        }
        # if logging.DEBUG >= logging.root.level:
        #     args['debug'] = True

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
            #Make sure the domain name is properly substituted.
            return evaluated_setting.replace('@', domain_name)

    def Backup(this):
        backup_file = this.CreateFile(
            os.path.join(this.buildPath, this.backup_path, f"Cloudflare-bak_{EOT.GetStardate()}.txt"))

        page_number = 0
        while True:
            page_number += 1
            # raw_results = this.cf.zones.get(params={'per_page': 2, 'page': page_number}) #testing
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

                # break #testing

            total_pages = raw_results['result_info']['total_pages']
            if page_number == total_pages:
                break

        backup_file.close()

    def Update(this):
        page_number = 0
        while True:
            page_number += 1
            # raw_results = this.cf.zones.get(params={'per_page': 2, 'page': page_number}) #testing
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
                    # break #testing

                    ############ BEGIN DNS SETTINGS ############
                    if 'dns' in setting:
                        time.sleep(1)  # rate limiting

                        for i, dns in enumerate(setting['dns']):

                            # rate limiting. keep us under 4 / sec.
                            # if (not i % 2): #at limit (3 possible requests per iteration).
                            time.sleep(1)

                            logging.debug(f"Applying DNS Setting: {dns}")

                            if (('type' not in dns) or ('domain' not in dns) or ('content' not in dns)):
                                logging.error(f"Invalid dns entry: {dns}")
                                continue

                            params = {'name': dns['domain'], 'match': 'all'}
                            if (dns['type'] in this.dns_allows_multiple_records):
                                params['type'] = dns['type']
                            dns_records = this.cf.zones.dns_records.get(domain_id, params=params)['result']  # REQUEST
                            existing_record = None

                            #Check for the proper record to update.
                            #This logic is complex in order to handle cases where you want to replace an A record with a CNAME or some other record type transmutation.
                            if len(dns_records):
                                if (dns['type'] in this.dns_allows_multiple_records and 'update_term' in dns):
                                    for existing in dns_records:
                                        if (dns['domain'] == existing['name'] and dns['update_term'] in existing['content']):
                                            
                                            if (existing_record is not None): # duplicate record found
                                                logging.debug(f"Deleting duplicate record with: {existing_record['content']}")
                                                time.sleep(1) #Sleep just in case
                                                result = this.cf.zones.dns_records.delete(domain_id, existing['id']) #possible additional request: Delete
                                            else:
                                                existing_record = existing
                                                logging.debug(f"Will update existing {existing_record['type']} record containing: {existing_record['content']}")

                                    if existing_record is None:
                                        logging.debug(f"Could not find existing record matching {dns['domain']} and update_term {dns['update_term']}")
                                else:
                                    single_instance_dns_records = [d for d in dns_records if d['type'] not in this.dns_allows_multiple_records]
                                    if (len(single_instance_dns_records) == 1):
                                        existing_record = dns_records[0]
                                        logging.debug(f"Will update existing {existing_record['type']} record")
                                    else:
                                        for existing in single_instance_dns_records:
                                            if (dns['domain'] == existing['name'] and dns['type'] == existing['type']):
                                                existing_record = existing
                                                logging.debug(f"Multiple matches found for {dns['domain']}. Using existing {dns['type']} record.")
                                                break
                                    if existing_record is None:
                                        logging.warn(f"Could not find appropriate existing record for {dns['domain']}. Candidates were: {single_instance_dns_records}")
                            else:
                                logging.debug(f"No matching records found on {domain_name} with params: {params}")

                            record_data = {
                                'name': dns['domain'],
                                'type': dns['type'],
                                'content': dns['content']
                            }
                            if ((dns['type'] not in this.dns_allows_multiple_records) and (dns['content'].endswith(domain_name))):
                                record_data['proxied'] = True

                            try:
                                result = {}

                                if existing_record is not None:
                                    logging.info(f"Will delete existing record: {existing_record}")
                                    if (not this.dry_run):
                                        result = this.cf.zones.dns_records.delete(domain_id, existing_record['id']) #POSSIBLE REQUEST: Delete
                                        logging.info(f"Result: {result}")

                                logging.info(f"Will create {dns['type']} record {dns['domain']} in {domain_name}")
                                if (not this.dry_run):
                                    result = this.cf.zones.dns_records.post(domain_id, data=record_data)  # REQUEST: Create
                                    logging.info(f"Result: {result}")

                            except CloudFlare.exceptions.CloudFlareAPIError as e:
                                logging.error('API call failed (%d): %s\nData: %s' % (e, e, record_data))
                                if (this.errors_are_fatal):
                                    exit()
                                else:
                                    domains_with_errors.append(domain)
                    ############ END DNS SETTINGS ############

                    ############ BEGIN PAGE RULE SETTINGS ############
                    if 'page_rules' in setting:

                        time.sleep(1)  # rate limiting

                        #Unlike DNS, this result does not depend on params and can be cached.
                        params = {'match': 'all'}
                        page_rules = this.cf.zones.pagerules.get(domain_id, params=params)['result']  # REQUEST

                        for i, pgr in enumerate(setting['page_rules']):

                            # rate limiting. keep us under 4 / sec.
                            if (not i % 3):
                                time.sleep(1)

                            logging.debug(f"Applying Page Rule Setting: {pgr}")

                            # TODO: input checking.

                            # check for the proper rule to update.
                            rule_to_update = None
                            if len(page_rules):
                                for existing in page_rules:
                                    if pgr['url'] in [target['constraint']['value'] for target in existing['targets']]:
                                        rule_to_update = existing
                                        break

                            targets = [{"target": "url", "constraint": {"operator": "matches", "value": pgr['url']}}]
                            rule_data = {"status": "active", "priority": 1, "actions": pgr['actions'], "targets": targets}

                            try:
                                result = {}

                                if rule_to_update is not None:
                                    r_id = rule_to_update['id']

                                    logging.info(f"Will update {pgr['url']} in {domain_name}")
                                    if (not this.dry_run):
                                        result = this.cf.zones.pagerules.put(domain_id, r_id, data=rule_data) # REQUEST: Update
                                        logging.info(f"Result: {result}")

                                else:
                                    logging.info(f"No matching page rule found for {pgr['url']}")

                                    logging.info(f"Will create {pgr['url']} in {domain_name}")
                                    if (not this.dry_run):
                                        result = this.cf.zones.pagerules.post(domain_id, data=rule_data) # REQUEST: Create
                                        logging.info(f"Result: {result}")

                            except CloudFlare.exceptions.CloudFlareAPIError as e:
                                logging.error('API call failed (%d): %s\nData: %s' % (e, e, rule_data))
                                if (this.errors_are_fatal):
                                    exit()
                                else:
                                    domains_with_errors.append(domain)
                    ############ END PAGE RULE SETTINGS ############

                    ############ BEGIN FIREWALL RULE SETTINGS ############
                    #TODO: Filters require a separate api, so updating does not work. We have to wipe + create atm.

                    if 'firewall_rules' in setting:
                        time.sleep(1)  # rate limiting

                        #Unlike DNS, this result does not depend on params and can be cached.
                        firewall_rules = this.cf.zones.firewall.rules.get(domain_id)['result']  # REQUEST

                        for i, fwr in enumerate(setting['firewall_rules']):

                            # rate limiting. keep us under 4 / sec.
                            if (not i % 3):
                                time.sleep(1)

                            logging.debug(f"Applying Firewall Rule Setting: {fwr}")

                            # TODO: input checking.

                            # check for the proper rule to update.
                            rule_to_update = None
                            if len(firewall_rules):
                                for existing in firewall_rules:
                                    if fwr['name'] == existing['filter']['description']:
                                        rule_to_update = existing
                                        break

                            rule_data = [{
                                "action": fwr['action'],
                                "priority": fwr['priority'],
                                "paused": False,
                                "description": fwr['name'],
                                "filter": {
                                    "expression": fwr['expression'].replace("'", '"'),
                                    "paused": False,
                                    "description": fwr['name'],
                                }
                            }]

                            try:
                                result = {}

                                if rule_to_update is not None:
                                    raise Exception("Firewall rules cannot be updated at this time. They must be wiped and recreated.")
                                    # r_id = rule_to_update['id']
                                    #
                                    # logging.info(f"Will update {fwr['name']} in {domain_name}")
                                    # if (not this.dry_run):
                                    #     result = this.cf.zones.firewall.rules.put(domain_id, r_id, data=rule_data) #REQUEST: Update
                                    #     logging.info(f"Result: {result}")

                                else:
                                    logging.info(f"No matching firewall rule found for {fwr['name']}")

                                    logging.info(f"Will create {fwr['name']} in {domain_name}")
                                    if (not this.dry_run):
                                        result = this.cf.zones.firewall.rules.post(domain_id, data=rule_data) #REQUEST: Create
                                        logging.info(f"Result: {result}")

                            except CloudFlare.exceptions.CloudFlareAPIError as e:
                                logging.error('API call failed (%d): %s\nData: %s' % (e, e, rule_data))
                                if (this.errors_are_fatal):
                                    exit()
                                else:
                                    domains_with_errors.append(domain)
                        ############ END FIREWALL RULE SETTINGS ############

                logging.info(f"---- done with {domain_name} ----")

            # break  # testing

            total_pages = raw_results['result_info']['total_pages']
            if page_number == total_pages:
                break

        logging.info("Complete!")
        if (len(domains_with_errors)):
            logging.error(f"The following domains had errors: {domains_with_errors}")