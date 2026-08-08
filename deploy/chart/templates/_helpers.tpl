{{- define "portal.labels" -}}
app.kubernetes.io/part-of: support-ticket-portal
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "portal.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end }}

{{- define "portal.storageClass" -}}
{{- if .Values.persistence.storageClass }}
storageClassName: {{ .Values.persistence.storageClass | quote }}
{{- end }}
{{- end }}

{{- define "portal.host" -}}
{{- .Values.ingress.host | default (printf "%s-%s-portal.%s" .Values.url.namespace .Values.environment .Values.url.domain) -}}
{{- end }}

{{- define "portal.redmineHost" -}}
{{- .Values.redmineIngress.host | default (printf "%s-%s-redmine.%s" .Values.url.namespace .Values.environment .Values.url.domain) -}}
{{- end }}
