import os
import logging
import shutil
import re
import CloudFlare
from eot import EOT
from ebbs import Builder
from ebbs import OtherBuildError

class cloudflare_update(Builder):
    class Record:
        def __init__(self, name, data, search_term, record_type='TXT'):
            self.name = name
            self.data = data
            self.search_term = search_term
            self.record_type = record_type

    def __init__(this, name="Cloudflare Update"):
        super().__init__(name)

        #We don't use the local filesystem
        this.clearBuildPath = False
        this.supportedProjectTypes = []

        this.requiredKWArgs.append("cf_email")
        this.requiredKWArgs.append("cf_token") # global api key (TODO: can this work with other tokens?)

        this.optionalKWArgs["dmarc"] = {
            "v" : "DMARC1",
            "p" : "reject",
            "pct" : "100",
            "fo" : "1",
            "adkim" : "s",
            "aspf" : "s"
        }
        this.optionalKWArgs["spf"] = "v=spf1 include:_spf.google.com ~all" #TODO: Expand spf to take multiple values, like dmarc.
        this.optionalKWArgs["backup"] = True
        this.optionalKWArgs["backup_path"] = "bak"

    #Required Builder method. See that class for details.
    def Build(this):
        this.Validate()
        this.Authenticate()
        if (this.backup):
            this.Backup()
        this.Update()

    #Make sure we have what we need.
    #Raise errors for anything wrong or missing.
    #RETURN void.
    def Validate(this):
        if (len(this.dmarc) and "rua" not in this.dmarc):
            errMsg = f"You must specify \"rua\" in dmarc settings. Got: {this.dmarc}"
            logging.error(errMsg)
            raise OtherBuildError(errMsg)

    #Create this.cf.
    def Authenticate(this):
        this.cf = CloudFlare.CloudFlare(email=this.cf_email, token=this.cf_token, raw=True)

    def Backup(this):
        backup_file = this.CreateFile(os.path.join(this.buildPath,this.backup_path,f"cloudflare-bak_{EOT.GetStardate()}.txt"))

        page_number = 0
        while True:
            page_number += 1
            raw_results = this.cf.zones.get(params={'per_page': 20, 'page': page_number})
            zones = raw_results['result']

            for zone in zones:
                zone_id = zone['id']
                zone_name = zone['name']
                logging.info(f"{zone_name}: {zone_id}")

                try:
                    dns_records = this.cf.zones.dns_records.get(zone_id)['result']

                    for r in dns_records:
                        logging.info(f"got record: {r}")
                        backup_file.write(f"{zone_name} ({zone_id}): {r}\n")

                except CloudFlare.exceptions.CloudFlareAPIError as e:
                    logging.error('/zones/dns_records.get %d %s - api call failed' % (e, e))

                logging.info(f"---- done with {zone_name} ----")

            # for testing
            # break

            total_pages = raw_results['result_info']['total_pages']
            if page_number == total_pages:
                break

        backup_file.close()


    def Update(this):
        page_number = 0
        while True:
            page_number += 1
            raw_results = this.cf.zones.get(params={'per_page': 20, 'page': page_number})
            zones = raw_results['result']

            for zone in zones:
                zone_id = zone['id']
                zone_name = zone['name']
                logging.info(f"{zone_name}: {zone_id}")

                records = []

                if (len(this.dmarc)):
                    dmarc = cloudflare_update.Record(f"_dmarc.{zone_name}", "; ".join('='.join((key,val)) for (key,val) in this.dmarc.items()), "v=DMARC")
                    records.append(dmarc)
                
                if (len(this.spf)):
                    spf = cloudflare_update.Record(f"{zone_name}", this.spf, "v=spf")
                    records.append(spf)

                for r in records:
                    try:
                        params = {'name': r.name, 'match': 'all', 'type': r.record_type}
                        dns_records = this.cf.zones.dns_records.get(zone_id, params=params)['result']

                        # print(f"records: {dns_records}")

                        new_record_data = {
                            'name': r.name,
                            'type': r.record_type,
                            'content': r.data,
                        }

                        dns_record = None

                        # check for the proper record to update.
                        if len(dns_records):
                            for existing in dns_records:
                                if r.search_term in existing['content']:
                                    dns_record = existing
                                    logging.info(f"Will update {existing['content']} to {r.data}")
                                    break

                        if dns_record is not None:
                            # then all the DNS records for that zone
                            # for dns_record in dns_records['result']:
                            #     print(f"record: {dns_record}")
                            r_name = dns_record['name']
                            r_type = dns_record['type']
                            r_value = dns_record['content']
                            r_id = dns_record['id']
                            logging.debug(f"Record: id: {r_id}, name: {r_name}, type: {r_type}, value: {r_value}")

                            updated_record = this.cf.zones.dns_records.put(zone_id, r_id, data=new_record_data)

                            logging.info(f"{r.name} updated for zone: {zone_name}; {updated_record}")

                        else:
                            logging.info(f"No record found matching {r.name}, {r.record_type}")
                            new_record = this.cf.zones.dns_records.post(zone_id, data=new_record_data)
                            logging.info(f"{r.name} created for zone: {zone_name}; {new_record}")

                    except CloudFlare.exceptions.CloudFlareAPIError as e:
                        exit('/zones/dns_records.get %d %s - api call failed' % (e, e))

                logging.info(f"---- done with {zone_name} ----")

            # for testing
            # break

            total_pages = raw_results['result_info']['total_pages']
            if page_number == total_pages:
                break
