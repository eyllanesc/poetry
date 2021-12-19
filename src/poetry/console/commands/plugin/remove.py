from cleo.helpers import argument
from cleo.helpers import option

from poetry.console.commands.command import Command
from poetry.console.commands.plugin.plugin_command_mixin import PluginCommandMixin
from poetry.locations import home_dir


class PluginRemoveCommand(Command, PluginCommandMixin):

    name = "plugin remove"

    description = "Removes installed plugins"

    arguments = [
        argument("plugins", "The names of the plugins to install.", multiple=True),
    ]

    options = [
        option(
            "dry-run",
            None,
            "Output the operations but do not execute anything (implicitly enables --verbose).",
        )
    ]

    def handle(self) -> int:
        import tomlkit

        from poetry.utils.env import EnvManager
        from poetry.utils.helpers import canonicalize_name

        plugins = self.argument("plugins")

        system_env = EnvManager.get_system_env(naive=True)
        env_dir = home_dir()

        existing_plugins = {}
        if env_dir.joinpath("plugins.toml").exists():
            existing_plugins = tomlkit.loads(
                env_dir.joinpath("plugins.toml").read_text(encoding="utf-8")
            )

        root_package = self.create_env_package(system_env, existing_plugins)

        entrypoints = self.get_plugin_entry_points()

        removed_plugins = []
        for plugin in plugins:
            plugin = canonicalize_name(plugin)
            is_plugin = any(
                canonicalize_name(entrypoint.distro.name) == plugin
                for entrypoint in entrypoints
            )
            installed = any(
                dependency.name == plugin for dependency in root_package.requires
            )

            if not installed:
                self.line_error(f"<warning>Plugin {plugin} is not installed.</warning>")

                continue

            if not is_plugin:
                self.line_error(
                    f"<warning>The package {plugin} is not a plugin.</<warning>"
                )
                continue

            if plugin in existing_plugins:
                del existing_plugins[plugin]

            removed_plugins.append(plugin)

        if not removed_plugins:
            return 1

        bare_root_package = root_package.with_dependency_groups([], only=True)
        for dependency in root_package.requires:
            if dependency.name not in removed_plugins:
                bare_root_package.add_dependency(dependency)

        return_code = self.update(
            system_env,
            bare_root_package,
            self._io,
            whitelist=removed_plugins,
        )

        if return_code != 0 or self.option("dry-run"):
            return return_code

        env_dir.joinpath("plugins.toml").write_text(
            tomlkit.dumps(existing_plugins, sort_keys=True), encoding="utf-8"
        )

        return 0
