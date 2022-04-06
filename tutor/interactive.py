from typing import List

import click

from . import config as tutor_config
from . import env, exceptions, fmt
from .types import Config, get_typed


def load_user_config(
    root: str, interactive: bool = True, dev_context: bool = False
) -> Config:
    """
    Load configuration and interactively ask questions to collect param values from the user.
    """
    config = tutor_config.load_minimal(root)
    defaults = tutor_config.get_defaults(config)
    prod = should_configure_for_prod(config, interactive, dev_context=dev_context)

    if prod:
        if interactive:
            prompt_and_configure_prod_host(config, defaults)
    else:
        configure_dev_host(config)

    if interactive:
        prompt_and_configure_platform_details(config, defaults)

    return config


def should_configure_for_prod(
    config: Config, interactive: bool, dev_context: bool
) -> bool:
    if dev_context:
        # If we're running from a `tutor dev ...` command, then just assume
        # that we're *not* configuring a production platform.
        return False
    already_configured_for_dev = config.get("LMS_HOST") == "local.overhang.io"
    if not interactive:
        return not already_configured_for_dev
    return click.confirm(
        fmt.question(
            "Are you configuring a production platform? Type 'n' if you are just testing Tutor on your local computer"
        ),
        prompt_suffix=" ",
        default=(not already_configured_for_dev),
    )


def configure_dev_host(config: Config) -> None:
    dev_values: Config = {
        "LMS_HOST": "local.overhang.io",
        "CMS_HOST": "studio.local.overhang.io",
        "ENABLE_HTTPS": False,
    }
    fmt.echo_info(
        """As you are not running this platform in production, we automatically set the following configuration values:"""
    )
    for k, v in dev_values.items():
        config[k] = v
        fmt.echo_info("    {} = {}".format(k, v))


def prompt_and_configure_prod_host(config: Config, defaults: Config) -> None:
    ask("Your website domain name for students (LMS)", "LMS_HOST", config, defaults)
    lms_host = get_typed(config, "LMS_HOST", str)
    if "localhost" in lms_host:
        raise exceptions.TutorError(
            "You may not use 'localhost' as the LMS domain name. To run a local platform for testing purposes you should answer 'n' to the previous question."
        )
    ask("Your website domain name for teachers (CMS)", "CMS_HOST", config, defaults)
    ask_bool(
        "Activate SSL/TLS certificates for HTTPS access?",
        "ENABLE_HTTPS",
        config,
        defaults,
    )


def prompt_and_configure_platform_details(config: Config, defaults: Config) -> None:
    ask("Your platform name/title", "PLATFORM_NAME", config, defaults)
    ask("Your public contact email address", "CONTACT_EMAIL", config, defaults)
    ask_choice(
        "The default language code for the platform",
        "LANGUAGE_CODE",
        config,
        defaults,
        [
            "en",
            "am",
            "ar",
            "az",
            "bg-bg",
            "bn-bd",
            "bn-in",
            "bs",
            "ca",
            "ca@valencia",
            "cs",
            "cy",
            "da",
            "de-de",
            "el",
            "en-uk",
            "en@lolcat",
            "en@pirate",
            "es-419",
            "es-ar",
            "es-ec",
            "es-es",
            "es-mx",
            "es-pe",
            "et-ee",
            "eu-es",
            "fa",
            "fa-ir",
            "fi-fi",
            "fil",
            "fr",
            "gl",
            "gu",
            "he",
            "hi",
            "hr",
            "hu",
            "hy-am",
            "id",
            "it-it",
            "ja-jp",
            "kk-kz",
            "km-kh",
            "kn",
            "ko-kr",
            "lt-lt",
            "ml",
            "mn",
            "mr",
            "ms",
            "nb",
            "ne",
            "nl-nl",
            "or",
            "pl",
            "pt-br",
            "pt-pt",
            "ro",
            "ru",
            "si",
            "sk",
            "sl",
            "sq",
            "sr",
            "sv",
            "sw",
            "ta",
            "te",
            "th",
            "tr-tr",
            "uk",
            "ur",
            "vi",
            "uz",
            "zh-cn",
            "zh-hk",
            "zh-tw",
        ],
    )


def ask(question: str, key: str, config: Config, defaults: Config) -> None:
    default = get_typed(defaults, key, str)
    default = get_typed(config, key, str, default=default)
    default = env.render_str(config, default)
    config[key] = click.prompt(
        fmt.question(question), prompt_suffix=" ", default=default, show_default=True
    )


def ask_bool(question: str, key: str, config: Config, defaults: Config) -> None:
    default = get_typed(defaults, key, bool)
    default = get_typed(config, key, bool, default=default)
    config[key] = click.confirm(
        fmt.question(question), prompt_suffix=" ", default=default
    )


def ask_choice(
    question: str,
    key: str,
    config: Config,
    defaults: Config,
    choices: List[str],
) -> None:
    default = str(config.get(key, defaults[key]))
    answer = click.prompt(
        fmt.question(question),
        type=click.Choice(choices),
        prompt_suffix=" ",
        default=default,
        show_choices=False,
    )
    config[key] = answer
