#! /usr/bin/env python3
import requests
import json
import re
import subprocess
from distutils.version import LooseVersion

def call_all_or_fail(*cmds):
    for cmd in cmds:
        retcode = subprocess.call(cmd)
        
        if retcode != 0:
            cmd_str = "".join(cmd)
            raise RuntimeError(f"non-zero ret code {retcode} returned for command {cmd_str}")
        
def update_tailscale():
    config_path = "tailscale/config.json"
    build_path = "tailscale/build.json"
    docker_path = "tailscale/Dockerfile"

    # read current config
    with open(config_path, "r") as f:
        config = json.loads(f.read())
    
    with open(build_path, "r") as f:
        build = json.loads(f.read())

    with open(docker_path, "r") as f:
        docker = f.read()

    local_version = LooseVersion(config['version'])
    print(f"current repo version: {local_version}")
    
    # Get the current requests page
    r = requests.get("https://pkgs.tailscale.com/stable/")
    r.raise_for_status()

    # version regex: 
    version_regex = re.compile('href\\w*=\\w*"tailscale_((?:\\d+\\.?)+)_[\\d\\w]+\\.tgz"')
    version_matches = set(version_regex.findall(r.text))

    try:
        remote_version = LooseVersion(version_matches.pop())
    except KeyError:
        raise RuntimeError("regex didn't match any versions on tailscale stable release page")

    if len(version_matches) != 0:
        raise RuntimeError("regex was ambiguous matching tailscale version")
    
    print(f"current upstream version: {remote_version}")

    if remote_version > local_version:
        # Pad new config version string to 4 parts
        config_version = str(remote_version)
        config_version += ".0" * (3 - config_version.count("."))

        print(f"upgrade required, new version: {config_version}")
        
        # set build version 
        build["args"]["TAILSCALE_VERSION"] = str(remote_version)

        # update build.json
        with open(build_path, "w") as f:
            f.write(json.dumps(build, indent=2))

        # update config.json
        config['version'] = config_version
        with open(config_path, "w") as f:
            f.write(json.dumps(config, indent=2))

        # update Dockerfile
        new_docker = re.sub('^ARG TAILSCALE_VERSION=.*$', 
            f"ARG TAILSCALE_VERSION=\"{remote_version}\"", 
            docker, flags=re.MULTILINE)

        with open(docker_path, "w") as f:
            f.write(new_docker)        

        # git add/commit/push
        call_all_or_fail(
            ["git", "add", config_path, docker_path, build_path],
            ["git", "commit", "-m", f"updated tailscale to {config_version}"]
        )

        return (local_version, config_version)
        
    else:
        print("no upgrade required")
        return None

if __name__ == "__main__":
    # git setup
    # call_all_or_fail(
    #     ["git", "config", "--local", "user.name", "update.py"],
    #     ["git", "config", "--local", "user.email", "update.py@hass-addons.git"]
    # )

    ts_ver_tpl = update_tailscale()

    # TODO email notify/push

