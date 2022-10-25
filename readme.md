# EBBS Cloudflare Updater

Ever wanted versioned dns records? This isn't quite that but we're getting closer. With the `cloudflare_update` build script, you'll be able to set your dns records from any of the ebbs config methods (e.g. build.json). When you run this script, you can backup your existing records and then apply the changes from your config. Pretty easy, right?

With this, you can currently update:
* DNS Records
* Page Rules
* Firewall Rules

Unfortunately, Cloudflare naming, features, and conventions are not entirely consistent (e.g. "dns_records" vs "pagerules" vs "firewall/rules"). As a result, this builder only supports a limited number of actions.

## Limitations
There are a few major limitations of the current implementation.

### No Way to Roll Back
Until recently Cloudflare had official mechanism for exporting nor importing dns records. Afaik, there is still no supported means of exporting and importing all domain settings (besides paying lots of money for an enterprise plan and having them do that for you). Because of this, the backup this script creates will require manual restoration if something goes wrong. All the information you need should be in the file, and hopefully soon this script will be able to read that file and manage rollbacks itself. However, that glorious day is yet to come.

### DNS

#### DNS Records Must Use `{domain_name}`
Cloudflare supports entering dns record names which are not fully qualified; however, it does not support getting records with a partial dns entry (creating `_config` will yield `_config.example.com` but getting `_config` from the `example.com` records does not produce `_config.example.com`).

To work around this issue an others, all instances of `{domain_name}` and `@` are replaced by the current domain's name before the request is sent. This maintains consistency with Cloudflare's current UI while only requiring you make your domains follow the `_config.{domain_name}` format. See below for an example.

When creating your DNS records, you can type "www.{domain_name}" or, simply "www.@"

**ALL @ SYMBOLS MUST BE ESCAPED WITH \\**

If you want to type an email, type "user\\@domain.ext"

#### No Ability to Delete DNS Records
We just don't support deleting or wiping dns records yet.

#### All DNS Records are Proxied
This is done for convenience. If you would like to change this behavior, please submit a pull request. 

### Firewall

#### Cloudflare Filters are Clobbered
Cloudflare currently only uses Filters for its Firewall. Because we're lazy and didn't implement multi-level update checks, the only way to update firewall rules is by wiping them (see below on `"wipe": ["firewall_rules"]`) and recreating them.

#### Firewall Rule Expressions Must Use `'`
Translating strings with quotes in them from json to python to a http request and then to Cloudflare's parsing utility is rather challenging. To make it simpler, this script requires that all quotes used in the `"firewall_rules"` `"expression"` value be single quotes (`'`). See below for an example.

### Building

#### Remember to Delete ./build (or Equivalent)
The config provided here (and recommended means of use) does not delete the `./build` folder. This is done to preserve the backup files created. However, if you update your build config, you will need to delete the build directory in order for ebbs to recreate it with the updated configuration.

## The _config DNS Record
To make this system work, you should create a `_config` TXT record on each Cloudflare domain containing a valid json string.
For example, `dig TXT _config.infrastructure.tech` shows we are using the following configuration:
```json
{
  "type": "primary",
  "security_level": 2
}
```
The `"type"` key is the required key but the value does not matter. Each of these values can be used in your record configuration by calling `domain_config['my_key']`. See below for an example. 

## build.json
The easiest way to use this builder is with a build.json file in the root of your project directory (see [ebbs](https://github.com/eons-dev/bin_ebbs) for more details).

Your build file should look something like:
```json
{
    "clear_build_path": false,
    "next":
    [
        {
            "build": "cloudflare_update",
            "build_in": "build",
            "run_when_any":
            [
                "release"
            ],
            "config":
            {
                "clear_build_path": false,
                "backup": true,
                "dry_run": true,
                "only_apply_to" :
                [
                    "example.com"
                ],
                "errors_are_fatal": true,
                "domains":
                [
                    {
                        "match":
                        {
                            "type": "primary"
                        },
                        "wipe":
                        [
                            "page_rules"
                        ],
                        "dns":
                        [
                            {
                                "type": "TXT",
                                "domain": "_dmarc.{domain_name}",
                                "content": "v=DMARC1; p=reject; pct=100; fo=1; adkim=s; aspf=s; rua=mailto:dmarc_agg\\@vali.email",
                                "update_term": "v=DMARC1"
                            },
                            {
                                "type": "TXT",
                                "domain": "{domain_name}",
                                "content": "v=spf1 include:_spf.google.com ~all",
                                "update_term": "v=spf1"
                            },
                            {
                                "type": "CNAME",
                                "domain": "www.{domain_name}",
                                "content": "{domain_name}"
                            }
                        ],
                        "page_rules":
                        [
                            {
                                "url": "www.{domain_name}/*",
                                "actions":
                                [
                                    {
                                        "id": "forwarding_url",
                                        "value":
                                        {
                                            "url": "https://{domain_name}/$1",
                                            "status_code": 301
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "match":
                        {
                            "type": "alias"
                        },
                        "wipe":
                        [
                            "page_rules"
                        ],
                        "dns":
                        [
                            {
                                "type": "CNAME",
                                "domain": "{domain_name}",
                                "content": "{domain_config['alias_of']}"
                            }
                        ],
                        "page_rules":
                        [
                            {
                                "url": "{domain_name}/*",
                                "actions":
                                [
                                    {
                                        "id": "forwarding_url",
                                        "value":
                                        {
                                            "url": "https://{domain_config['alias_of']}/$1",
                                            "status_code": 301
                                        }
                                    }
                                ]
                            },
                            {
                                "url": "www.{domain_name}/*",
                                "actions":
                                [
                                    {
                                        "id": "forwarding_url",
                                        "value":
                                        {
                                            "url": "https://{domain_config['alias_of']}/$1",
                                            "status_code": 301
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "match":
                        {
                            "security_level": 0
                        },
                        "wipe":
                        [
                            "firewall_rules"
                        ],
                        "firewall_rules":
                        [

                        ]
                    },
                    {
                        "match":
                        {
                            "security_level": 1
                        },
                        "wipe":
                        [
                            "firewall_rules"
                        ],
                        "firewall_rules":
                        [
                            {
                                "name": "Deny Admin",
                                "priority": 3,
                                "action": "block",
                                "expression": "(http.request.uri.path contains '/wp-json') or  (http.request.uri.path contains '/wp-admin') or ( http.request.uri.path contains 'author' and  not http.request.uri.path contains '-author' )"
                            },
                            {
                                "name": "Allow User Login",
                                "priority": 2,
                                "action": "allow",
                                "expression": "( (http.request.uri.path contains '/wp-admin/admin-ajax.php') or (http.request.uri.path contains '/wp-admin/js/') or (http.request.uri.path contains '/wp-admin/css/') )"
                            },
                            {
                                "name": "Allow Admin",
                                "priority": 1,
                                "action": "allow",
                                "expression": "( (http.request.uri.path contains 'wp-json') or (http.request.uri.path contains 'wp-admin') ) and ( cf.threat_score lt 3 )"
                            }
                        ]
                    }
                ]
            },
            "next":
            [
                {
                    "build": "publish",
                    "build_in": "bak",
                    "config":
                    {
                        "clear_build_path": false,
                        "visibility": "private"
                    }
                }
            ]
        }
    ]
}
```

### "dry_run"
Note the `"dry_run": true`. If you want to run this code live, change that to `"dry_run": false`.

Specifying `"dry_run": true` will limit Cloudflare API calls to GET requests only.

### "only_apply_to"
If you want to adjust a subset of your domains, simply specify the domain names in the `"only_apply_to": []` list. 

Leaving the `"only_apply_to": []` list empty or removing it will cause this script to act on all domains.

### "errors_are_fatal"
If you have a lot of domains and don't want to debug each one or want to gloss over some known issue, set `"errors_are_fatal": false`. Doing this will cause errors to only be reported to you and will not hault execution.

Doing this is generally not recommended (obviously).

### Other Notes on EBBS
The `run_when_any:["release"]` code is intended for github releases. If you would like to keep this functionality, it is recommended to use the [ebbs github workflows](https://github.com/eons-dev/part_ebbs-workflows), which will provide `--event release` on release creation. NOTE: if you use the ebbs workflows, you should edit them to provide `cf_email` and `cf_token` as environment variables (usually from github secrets).

To take advantage of the `publish` mechanic for uploading the latest backup, you must have a valid infrastructure.tech account or use your own repository. Currently, the infrastructure.tech frontend is under development, so if you would like an account or even help getting started, email support@infrastructure.tech.
