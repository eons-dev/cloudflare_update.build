# EBBS Workflows for GitHub

Use [ebbs](https://github.com/eons-dev/bin_ebbs) for your git repo!

## Usage

### build.json
Make sure you have a valid build.json in the root of your directory. This would be something like:

```json
{
  "clear_build_path" : true,
  "ebbs_next": [
    {
      "build" : "publish",
      "run_when" : "release",
      "copy" : [
        {"../inc/" : "inc/"}
      ],
      "config" : {
        "visibility" : "public"
      }
    }
  ]
}
```


### Subrepo

Make sure the workflow files are present in your .github/workflows folder.

Clone with [subrepo](https://github.com/ingydotnet/git-subrepo):
```
mkdir -p .github/workflows
git subrepo clone https://github.com/eons-dev/part_ebbs-workflows.git .github/workflows
```

### Additional Notes:

These workflows provide the following events:
 * "release"
 * "push"
 * "pull_request"

Any of those events can be used with the "run_when" json var, allowing you to use a single build.json for all your workflows.

If you would like additional environment variables, cli args, build steps, etc, you can always clone this repo or modify the subrepo clone to your liking.
