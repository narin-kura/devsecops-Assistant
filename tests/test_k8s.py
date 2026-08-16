"""Coverage for generate_k8s_manifests() / generate_helm_chart(): detect -> profile -> render -> write.

The Helm chart case has a specific regression to guard: templates/*.yaml
must keep their "{{ .Values.x }}" Go-template syntax completely untouched
(Helm re-renders it at install time), while "[[ service_name ]]"-style
placeholders must be substituted -- the inverse of, but same class of bug
as, the earlier GitHub Actions template issue where a Jinja variable got
swallowed by a raw block instead of rendered.
"""

import yaml

from core.modules.containerize.k8s import generate_helm_chart, generate_k8s_manifests


def _python_project(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    return tmp_path


def test_manifests_render_valid_yaml_and_use_detected_port(tmp_path):
    _python_project(tmp_path)
    result = generate_k8s_manifests(str(tmp_path), dry_run=True)

    deployment = yaml.safe_load(result.rendered["deployment"])
    service = yaml.safe_load(result.rendered["service"])

    assert deployment["kind"] == "Deployment"
    assert deployment["spec"]["replicas"] == 2
    assert deployment["spec"]["template"]["spec"]["containers"][0]["ports"][0]["containerPort"] == 5000
    assert service["spec"]["ports"][0]["port"] == 5000


def test_manifests_use_placeholder_image_by_default(tmp_path):
    # NOTE: service_name is slugified (e.g. "_" -> "-"), so it can differ
    # from the raw tmp_path directory name -- compare against the profile's
    # own service_name rather than assuming they match.
    _python_project(tmp_path)
    result = generate_k8s_manifests(str(tmp_path), dry_run=True)

    deployment = yaml.safe_load(result.rendered["deployment"])
    expected_image = f"{result.container.service_name}:latest"
    assert deployment["spec"]["template"]["spec"]["containers"][0]["image"] == expected_image


def test_manifests_honor_explicit_image_port_and_replicas(tmp_path):
    _python_project(tmp_path)
    result = generate_k8s_manifests(str(tmp_path), port=9999, replicas=3, image="ghcr.io/org/app:v1", dry_run=True)

    deployment = yaml.safe_load(result.rendered["deployment"])
    assert deployment["spec"]["replicas"] == 3
    assert deployment["spec"]["template"]["spec"]["containers"][0]["image"] == "ghcr.io/org/app:v1"
    assert deployment["spec"]["template"]["spec"]["containers"][0]["ports"][0]["containerPort"] == 9999


def test_manifests_dry_run_does_not_write(tmp_path):
    _python_project(tmp_path)
    generate_k8s_manifests(str(tmp_path), dry_run=True)

    assert not (tmp_path / "k8s").exists()


def test_manifests_write_to_default_and_custom_directories(tmp_path):
    _python_project(tmp_path)
    result = generate_k8s_manifests(str(tmp_path), dry_run=False)

    assert (tmp_path / "k8s" / "deployment.yaml").exists()
    assert (tmp_path / "k8s" / "service.yaml").exists()
    assert result.written_paths["deployment"] == tmp_path / "k8s" / "deployment.yaml"

    custom_dir = tmp_path / "manifests"
    result2 = generate_k8s_manifests(str(tmp_path), output_dir=str(custom_dir), dry_run=False)
    assert (custom_dir / "deployment.yaml").exists()
    assert result2.written_paths["deployment"] == custom_dir / "deployment.yaml"


def test_helm_chart_yaml_and_values_render_valid_yaml(tmp_path):
    _python_project(tmp_path)
    result = generate_helm_chart(str(tmp_path), dry_run=True)

    chart = yaml.safe_load(result.rendered["Chart.yaml"])
    values = yaml.safe_load(result.rendered["values.yaml"])

    assert chart["name"] == result.container.service_name
    assert values["replicaCount"] == 2
    assert values["service"]["port"] == 5000


def test_helm_templates_keep_go_template_syntax_intact(tmp_path):
    _python_project(tmp_path)
    result = generate_helm_chart(str(tmp_path), dry_run=True)

    deployment = result.rendered["templates/deployment.yaml"]
    service = result.rendered["templates/service.yaml"]

    # Go-template expressions must survive completely untouched -- Helm
    # renders these at install time, not us.
    assert "{{ .Values.replicaCount }}" in deployment
    assert "{{ .Values.image.repository }}:{{ .Values.image.tag }}" in deployment
    assert "{{- toYaml .Values.resources | nindent 12 }}" in deployment
    assert "{{ .Values.service.type }}" in service

    # Our own substitution markers must be gone, replaced with real values.
    assert "[[" not in deployment and "]]" not in deployment
    assert "[[" not in service and "]]" not in service
    assert f"name: {result.container.service_name}" in deployment


def test_helm_chart_honors_custom_replicas_and_port(tmp_path):
    _python_project(tmp_path)
    result = generate_helm_chart(str(tmp_path), port=9999, replicas=5, dry_run=True)

    values = yaml.safe_load(result.rendered["values.yaml"])
    assert values["replicaCount"] == 5
    assert values["service"]["port"] == 9999


def test_helm_chart_dry_run_does_not_write(tmp_path):
    _python_project(tmp_path)
    generate_helm_chart(str(tmp_path), dry_run=True)

    assert not (tmp_path / "chart").exists()


def test_helm_chart_writes_full_directory_structure(tmp_path):
    _python_project(tmp_path)
    result = generate_helm_chart(str(tmp_path), dry_run=False)

    chart_dir = tmp_path / "chart"
    assert (chart_dir / "Chart.yaml").exists()
    assert (chart_dir / "values.yaml").exists()
    assert (chart_dir / ".helmignore").exists()
    assert (chart_dir / "templates" / "deployment.yaml").exists()
    assert (chart_dir / "templates" / "service.yaml").exists()
    assert result.written_paths["templates/deployment.yaml"] == chart_dir / "templates" / "deployment.yaml"


def test_minimal_signal_project_still_renders_both_kinds(tmp_path):
    (tmp_path / "README.md").write_text("nothing recognizable\n", encoding="utf-8")

    manifests = generate_k8s_manifests(str(tmp_path), dry_run=True)
    helm = generate_helm_chart(str(tmp_path), dry_run=True)

    assert manifests.rendered["deployment"].strip()
    assert helm.rendered["Chart.yaml"].strip()
