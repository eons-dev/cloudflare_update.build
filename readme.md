# EBBS Cloudflare Updater

Ever wanted versioned dns records? This isn't quite that but we're getting closer. With the `cloudflare_update` build script, you'll be able to set your dns records from any of the ebbs config methods (e.g. build.json). When you run this script, you can backup your existing records and then apply the changes from your config. Pretty easy, right?

With this, you can currently update:
* DMARC
* SPF

Unfortunately, Cloudflare does not make all of its api calls available to free accounts. This prevents us from implementing things like firewall rule updates. With that said, if you would like to add in the logic for handling paid api calls, please make a pull request! Surely other's on paid accounts will appreciate full access to their features.

## build.json
The easiest way to use this builder is with a build.json file in the root of your project directory (or in a build folder if you adjust the copy file paths).
That file should look something like:
```json
{
  "clear_build_path" : false,
  "ebbs_next": [
	{
	  "build" : "cloudflare_update",
	  "build_in" : "build",
	  "run_when" : [
		"release"
	  ],
	  "config" : {
		"clear_build_path" : false,
		"backup" : true,
		"dmarc" : {
			"v" : "DMARC1",
			"p" : "reject",
			"pct" : "100",
			"fo" : "1",
			"adkim" : "s",
			"aspf" : "s",
			"rua" : "mailto:YOUREMAIL@YOURDOMAIN.TLD"
		},
		"spf" : "v=spf1 include:_spf.google.com ~all",
		"ebbs_next": [
            {
    		  "build" : "publish",
    		  "build_in" : "bak",
    		  "config" : {
    			"clear_build_path" : false,
    			"visibility" : "private"
			}
		  }
		]
	  }
	}
  ]
}
```
The `run_when:["release"]` code is intended for github releases. If you would like to keep this functionality, it is recommended to use the [ebbs github workflows](https://github.com/eons-dev/part_ebbs-workflows), which will provide `--event release` on release creation. NOTE: if you use the ebbs workflows, you should edit them to provide `cf_email` and `cf_token` as environment variables (usually from github secrets).

To take advantage of the `publish` mechanic for uploading the latest backup, you must have a valid infrastructure.tech account or use your own repository. Currently, the infrastructure.tech frontend is under development, so if you would like an account or even help getting started, email support@infrastructure.tech.
