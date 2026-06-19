
# Add system packages
tesseract
mesa-libGL
poppler-utils
graphviz

# Add Properties
dku.feature.agentDiagram.enabled	true
dku.feature.aiExplain.enabled	true
dku.feature.aiPrepare.enabled	true
dku.feature.codeAssistant.enabled	true
dku.feature.docportal.enabled	true
dku.feature.GOVERN_INTEGRATION.enabled	true
dku.feature.llmCoreSupport.enabled	true
dku.feature.llmEvaluation.enabled	true
dku.feature.llmFineTuningExperimentalSupport.enabled	true
dku.feature.llmFineTuningSupport.enabled	true
dku.feature.story.enabled	true
dku.feature.streaming.enabled	true
dku.feature.testingWithDss.enabled	true
dku.kubernetes.jobs.extraAnnotations    [{key: karpenter.sh/do-not-disrupt, value: true}]
dku.llm.embedDocuments.screenshotPaginationSize 30

## increasing LLM Mesh caching size and duration
dku.llm.cache.completion.diskCachedMB   8192
dku.llm.cache.completion.cacheExpirationMinutes 3200
dku.llm.cache.embeddings.diskCachedMB   8192
dku.llm.cache.embeddings.cacheExpirationMinutes 43200




# Ansible task - Install dss-plugin-hierarchical-charts plugin
---
- name: Fetch DSS system facts
  become: true
  become_user: dataiku
  dataiku.dss.dss_system_facts:
    datadir: /data/dataiku/dss_data
  register: dss_system_facts

- name: Configure Kubernetes settings
  when: dss_system_facts.install_ini.general.nodetype == "design" or dss_system_facts.install_ini.general.nodetype == "automation"
  block:
    - name: Install dss-plugin-hierarchical-charts plugin from git 
      dataiku.dss.dss_plugin:
        state: present
        plugin_id: hierarchical-charts
        git_repository_url: https://github.com/dataiku/dss-plugin-hierarchical-charts.git
        git_checkout: master


# Ansible task - install tailscale
---
- name: Tailscale | Install DNF Dependencies
  become: true
  ansible.builtin.dnf:
    name:
      - yum-utils
      - gnupg
    state: present

- name: Tailscale | Add Tailscale Repo
  become: true
  ansible.builtin.command: "dnf config-manager --add-repo https://pkgs.tailscale.com/stable/centos/{{ ansible_distribution_major_version }}/tailscale.repo"
  args:
    creates: /etc/yum.repos.d/tailscale.repo

- name: Tailscale | Install Tailscale
  become: true
  ansible.builtin.dnf:
    name: tailscale
    state: latest

- name: Tailscale | Create systemd customization directory
  become: true
  ansible.builtin.file:
    path: /etc/systemd/system/tailscaled.service.d
    state: directory
    mode: "644"
    owner: root
    group: root

- name: Tailscale | Customize tailscaled systemd service
  become: true
  ansible.builtin.copy:
    dest: /etc/systemd/system/tailscaled.service.d/override.conf
    content: |
      [Service]
      ExecStart=
      ExecStart=/usr/sbin/tailscaled --state=/data/etc/tailscale/tailscaled.state --socket=/run/tailscale/tailscaled.sock --port=${PORT} $FLAGS
    mode: "644"
    owner: root
    group: root

- name: Tailscale | Enable Service
  become: true
  ansible.builtin.service:
    name: tailscaled
    state: started
    enabled: true


# Ansible task - AWS Cloudwatch Agent
- name: CloudWatch Agent | Download RPM
  become: true
  get_url:
    url: https://s3.amazonaws.com/amazoncloudwatch-agent/redhat/amd64/latest/amazon-cloudwatch-agent.rpm
    dest: /tmp/amazon-cloudwatch-agent.rpm
    mode: '0644'

- name: CloudWatch Agent | Install RPM
  become: true
  yum:
    name: /tmp/amazon-cloudwatch-agent.rpm
    state: present
    disable_gpg_check: true

- name: CloudWatch Agent | Write config
  become: true
  copy:
    dest: /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
    content: |
      {
        "metrics": {
          "namespace": "CWAgent",
          "append_dimensions": { "InstanceId": "${aws:InstanceId}" },
          "metrics_collected": {
            "disk": {
              "measurement": ["disk_used_percent", "disk_used", "disk_total"],
              "metrics_collection_interval": 300,
              "resources": ["/", "/data"]
            },
            "mem": {
              "measurement": ["mem_used_percent", "mem_used", "mem_total"],
              "metrics_collection_interval": 300
            }
          }
        }
      }
    mode: '0644'
  register: cw_config

- name: CloudWatch Agent | Apply config and start
  become: true
  command: >
    /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl
    -a fetch-config -m ec2
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
    -s
  when: cw_config.changed

