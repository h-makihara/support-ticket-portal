{{- define "portal.backendDeployment" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $slot := .slot -}}
{{- $legacy := .legacy -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $name }}
  labels:
    {{- include "portal.labels" $root | nindent 4 }}
    {{- if not $legacy }}
    app.kubernetes.io/slot: {{ $slot }}
    {{- end }}
spec:
  replicas: {{ $root.Values.app.replicas }}
  selector:
    matchLabels:
      app.kubernetes.io/name: backend
      app.kubernetes.io/instance: {{ $root.Release.Name }}
      {{- if not $legacy }}
      app.kubernetes.io/slot: {{ $slot }}
      {{- end }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: backend
        app.kubernetes.io/instance: {{ $root.Release.Name }}
        app.kubernetes.io/slot: {{ $slot }}
      annotations:
        checksum/secrets: {{ toJson $root.Values.secrets | sha256sum }}
        {{- if $root.Values.observability.enabled }}
        checksum/otel-sidecar-config: {{ toJson $root.Values.observability | sha256sum }}
        {{- end }}
    spec:
      {{- with $root.Values.imagePullSecrets }}
      imagePullSecrets: {{ toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: backend
          image: "{{ $root.Values.images.backend.repository }}:{{ .backendTag | default $root.Values.images.backend.tag }}"
          imagePullPolicy: {{ $root.Values.images.backend.pullPolicy }}
          env:
            - {name: REDMINE_BASE_URL, value: "http://redmine:3000"}
            - name: REDMINE_API_KEY
              valueFrom:
                secretKeyRef: {name: support-ticket-portal-secrets, key: REDMINE_API_KEY}
            - {name: REDMINE_PROJECT_ID, value: {{ $root.Values.app.redmineProjectId | quote }}}
            - {name: REDMINE_TRACKER_ID, value: {{ $root.Values.app.redmineTrackerId | quote }}}
            - {name: REDIS_URL, value: "redis://redis:6379/0"}
            - {name: SESSION_COOKIE_SECURE, value: {{ $root.Values.app.sessionCookieSecure | quote }}}
            - {name: CORS_ORIGINS, value: {{ printf "%s://%s" (ternary "https" "http" $root.Values.ingress.tls.enabled) (include "portal.host" $root) | quote }}}
            {{- if $root.Values.observability.enabled }}
            - {name: LOG_LEVEL, value: "DEBUG"}
            - {name: OTEL_EXPORTER_OTLP_ENDPOINT, value: "http://localhost:4318"}
            - {name: OTEL_EXPORTER_OTLP_PROTOCOL, value: "http/protobuf"}
            - {name: OTEL_RESOURCE_ATTRIBUTES, value: {{ printf "deployment.environment.name=%s,deployment.slot=%s" $root.Values.environment $slot | quote }}}
            {{- else }}
            - {name: OTEL_SDK_DISABLED, value: "true"}
            {{- end }}
            {{- range $envName, $value := $root.Values.app.backendEnv }}
            - name: {{ $envName }}
              value: {{ $value | toString | quote }}
            {{- end }}
          ports:
            - name: http
              containerPort: 8000
          readinessProbe:
            httpGet: {path: /health, port: http}
            initialDelaySeconds: 5
            periodSeconds: 10
          resources: {{ toYaml $root.Values.resources.backend | nindent 12 }}
        {{- if $root.Values.observability.enabled }}
        - name: otel-collector
          image: "{{ $root.Values.images.otelCollector.repository }}:{{ $root.Values.images.otelCollector.tag }}"
          imagePullPolicy: {{ $root.Values.images.otelCollector.pullPolicy }}
          args: ["--config=/etc/otelcol/config.yaml"]
          ports:
            - {name: otlp-http, containerPort: 4318}
            - {name: health, containerPort: 13133}
          readinessProbe:
            httpGet: {path: /, port: health}
            initialDelaySeconds: 2
            periodSeconds: 10
          resources: {{ toYaml $root.Values.resources.otelCollector | nindent 12 }}
          volumeMounts:
            - {name: otel-sidecar-config, mountPath: /etc/otelcol}
        {{- end }}
      {{- if $root.Values.observability.enabled }}
      volumes:
        - name: otel-sidecar-config
          configMap: {name: backend-otel-collector-config}
      {{- end }}
{{- end }}

{{- define "portal.frontendDeployment" -}}
{{- $root := .root -}}
{{- $name := .name -}}
{{- $slot := .slot -}}
{{- $legacy := .legacy -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $name }}
  labels:
    {{- include "portal.labels" $root | nindent 4 }}
    {{- if not $legacy }}
    app.kubernetes.io/slot: {{ $slot }}
    {{- end }}
spec:
  replicas: {{ $root.Values.app.replicas }}
  selector:
    matchLabels:
      app.kubernetes.io/name: frontend
      app.kubernetes.io/instance: {{ $root.Release.Name }}
      {{- if not $legacy }}
      app.kubernetes.io/slot: {{ $slot }}
      {{- end }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: frontend
        app.kubernetes.io/instance: {{ $root.Release.Name }}
        app.kubernetes.io/slot: {{ $slot }}
      {{- if not $legacy }}
      annotations:
        checksum/frontend-nginx-config: {{ include "portal.frontendConfig" (dict "slot" $slot) | sha256sum }}
      {{- end }}
    spec:
      {{- with $root.Values.imagePullSecrets }}
      imagePullSecrets: {{ toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: frontend
          image: "{{ $root.Values.images.frontend.repository }}:{{ .frontendTag | default $root.Values.images.frontend.tag }}"
          imagePullPolicy: {{ $root.Values.images.frontend.pullPolicy }}
          ports:
            - name: http
              containerPort: 80
          readinessProbe:
            httpGet: {path: /, port: http}
            periodSeconds: 10
          resources: {{ toYaml $root.Values.resources.frontend | nindent 12 }}
          {{- if not $legacy }}
          volumeMounts:
            - name: nginx-config
              mountPath: /etc/nginx/conf.d/default.conf
              subPath: default.conf
          {{- end }}
      {{- if not $legacy }}
      volumes:
        - name: nginx-config
          configMap:
            name: frontend-{{ $slot }}-nginx
      {{- end }}
{{- end }}
