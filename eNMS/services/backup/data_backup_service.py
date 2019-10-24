from datetime import datetime
from pathlib import Path
from re import M, sub
from sqlalchemy import Boolean, Float, ForeignKey, Integer
from wtforms import HiddenField, StringField

from eNMS.database.dialect import Column, SmallString
from eNMS.database.functions import factory
from eNMS.forms.automation import NetmikoForm
from eNMS.models.automation import ConnectionService


class DataBackupService(ConnectionService):

    __tablename__ = "data_backup_service"
    pretty_name = "Data Backup"

    id = Column(Integer, ForeignKey("connection_service.id"), primary_key=True)
    enable_mode = Column(Boolean, default=True)
    config_mode = Column(Boolean, default=False)
    commands = Column(LargeString)
    driver = Column(SmallString)
    use_device_driver = Column(Boolean, default=True)
    fast_cli = Column(Boolean, default=False)
    timeout = Column(Integer, default=10.0)
    global_delay_factor = Column(Float, default=1.0)
    regex_pattern_1 = Column(SmallString)
    regex_replace_1 = Column(SmallString)
    regex_pattern_2 = Column(SmallString)
    regex_replace_2 = Column(SmallString)
    regex_pattern_3 = Column(SmallString)
    regex_replace_3 = Column(SmallString)

    __mapper_args__ = {"polymorphic_identity": "netmiko_backup_service"}

    def job(self, run, payload, device):
        try:
            commands = run.sub(run.commands, locals()).splitlines()
            device.last_runtime = datetime.now()
            path_device_data = Path.cwd() / "git" / "data" / device.name
            path_device_data.mkdir(parents=True, exist_ok=True)
            netmiko_connection = run.netmiko_connection(device)
            run.log("info", "Fetching Netmiko configuration", device)
            data = {}
            for command in commands:
                result = netmiko_connection.send_command(command)
                for i in range(1, 4):
                    result = sub(
                        getattr(self, f"regex_pattern_{i}"),
                        getattr(self, f"regex_replace_{i}"),
                        result,
                        flags=M,
                    )
                data[command] = result
            device.last_status = "Success"
            device.last_duration = (
                f"{(datetime.now() - device.last_runtime).total_seconds()}s"
            )
            if device.data == data:
                return {"success": True, "result": "no change"}
            device.last_update = str(device.last_runtime)
            factory(
                "data",
                device=device.id,
                runtime=device.last_runtime,
                duration=device.last_duration,
                data=data,
            )
            device.data = data
            with open(path_device_data / "data.yml", "w") as file:
                yaml.dump(data, file, default_flow_style=False)
            with open(path_device_data / device.name, "w") as file:
                file.write(app.str_dict(data))
            run.generate_yaml_file(path_device_data, device)
        except Exception as e:
            device.last_status = "Failure"
            device.last_failure = str(device.last_runtime)
            run.generate_yaml_file(path_device_data, device)
            return {"success": False, "result": str(e)}
        return {"success": True, "result": f"Command: {command}"}


class NetmikoBackupForm(NetmikoForm):
    form_type = HiddenField(default="netmiko_backup_service")
    configuration_command = StringField()
    regex_pattern_1 = StringField("First regex to change config results")
    regex_replace_1 = StringField("Value to replace first regex")
    regex_pattern_2 = StringField("Second regex to change config results")
    regex_replace_2 = StringField("Value to replace second regex")
    regex_pattern_3 = StringField("Third regex to change config results")
    regex_replace_3 = StringField("Value to replace third regex")
    groups = {
        "Main Parameters": {
            "commands": [
                "configuration_command",
                "regex_pattern_1",
                "regex_replace_1",
                "regex_pattern_2",
                "regex_replace_2",
                "regex_pattern_3",
                "regex_replace_1",
            ],
            "default": "expanded",
        },
        **NetmikoForm.groups,
    }
