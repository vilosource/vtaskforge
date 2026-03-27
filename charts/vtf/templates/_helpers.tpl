{{/*
Expand the name of the chart.
*/}}
{{- define "vtf.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "vtf.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels applied to every resource.
*/}}
{{- define "vtf.labels" -}}
helm.sh/chart: {{ include "vtf.name" . }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}

{{/*
Selector labels for a given component.
Usage: {{ include "vtf.selectorLabels" (dict "root" . "component" "api") }}
*/}}
{{- define "vtf.selectorLabels" -}}
app.kubernetes.io/name: {{ include "vtf.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Secret name used by all components.
*/}}
{{- define "vtf.secretName" -}}
{{ include "vtf.fullname" . }}-secrets
{{- end }}

{{/*
Database service name (built-in postgres).
*/}}
{{- define "vtf.dbName" -}}
{{ include "vtf.fullname" . }}-db
{{- end }}

{{/*
Redis service name (built-in redis).
*/}}
{{- define "vtf.redisName" -}}
{{ include "vtf.fullname" . }}-redis
{{- end }}

{{/*
Compute DATABASE_URL.
If database.databaseUrl is set explicitly, use it.
Otherwise build it from the built-in postgres service.
*/}}
{{- define "vtf.databaseUrl" -}}
{{- if .Values.database.databaseUrl -}}
  {{- .Values.database.databaseUrl -}}
{{- else -}}
  postgres://{{ .Values.database.user }}:{{ .Values.database.password }}@{{ include "vtf.dbName" . }}:5432/{{ .Values.database.name }}
{{- end -}}
{{- end }}

{{/*
Compute CELERY_BROKER_URL.
If broker.celeryBrokerUrl is set explicitly, use it.
Otherwise build it from the built-in redis service.
*/}}
{{- define "vtf.celeryBrokerUrl" -}}
{{- if .Values.broker.celeryBrokerUrl -}}
  {{- .Values.broker.celeryBrokerUrl -}}
{{- else -}}
  redis://{{ include "vtf.redisName" . }}:6379/0
{{- end -}}
{{- end }}

{{/*
Compute ALLOWED_HOSTS for the API.
Includes: localhost, service name, namespace-qualified names, ingress hosts, extras.
*/}}
{{- define "vtf.allowedHosts" -}}
localhost,127.0.0.1,{{ include "vtf.fullname" . }}-api,{{ include "vtf.fullname" . }}-api.{{ .Release.Namespace }},{{ include "vtf.fullname" . }}-api.{{ .Release.Namespace }}.svc.cluster.local
{{- if .Values.ingress.apiHost }},{{ .Values.ingress.apiHost }}{{ end -}}
{{- if .Values.api.extraAllowedHosts }},{{ .Values.api.extraAllowedHosts }}{{ end -}}
{{- end }}

{{/*
Common environment variables shared by api, mcp, celery, celery-beat, and migrate.
*/}}
{{- define "vtf.commonEnv" -}}
- name: DJANGO_SETTINGS_MODULE
  value: {{ .Values.django.settingsModule | quote }}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "vtf.secretName" . }}
      key: DATABASE_URL
- name: CELERY_BROKER_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "vtf.secretName" . }}
      key: CELERY_BROKER_URL
- name: SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "vtf.secretName" . }}
      key: SECRET_KEY
{{- end }}
