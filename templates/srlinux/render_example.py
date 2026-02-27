from jinja2 import Environment, FileSystemLoader
import yaml

env = Environment(loader=FileSystemLoader('.'))
vars = yaml.safe_load(open('templates/srlinux/example_vars.yaml'))
tmpl = env.get_template('templates/srlinux/full_config.j2')
print(tmpl.render(device=vars['device']))
