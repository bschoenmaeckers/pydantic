"""
Defining fields on models.
"""
from __future__ import annotations as _annotations

import dataclasses
import inspect
import sys
import typing
from copy import copy
from dataclasses import Field as DataclassField
from typing import Any
from warnings import warn

import annotated_types
import typing_extensions

from . import types
from ._internal import _decorators, _fields, _internal_dataclass, _repr, _typing_extra, _utils
from ._internal._fields import Undefined
from ._internal._generics import replace_types
from .errors import PydanticUserError

if typing.TYPE_CHECKING:
    from ._internal._repr import ReprArgs


class _FromFieldInfoInputs(typing_extensions.TypedDict, total=False):
    """
    This class exists solely to add typechecking for the `**kwargs` in `FieldInfo.from_field`.
    """

    annotation: type[Any] | None
    default_factory: typing.Callable[[], Any] | None
    alias: str | None
    alias_priority: int | None
    validation_alias: str | AliasPath | AliasChoices | None
    serialization_alias: str | None
    title: str | None
    description: str | None
    examples: list[Any] | None
    exclude: bool | None
    include: bool | None
    gt: float | None
    ge: float | None
    lt: float | None
    le: float | None
    multiple_of: float | None
    strict: bool | None
    min_length: int | None
    max_length: int | None
    pattern: str | None
    allow_inf_nan: bool | None
    max_digits: int | None
    decimal_places: int | None
    discriminator: str | None
    json_schema_extra: dict[str, Any] | None
    frozen: bool | None
    final: bool | None
    validate_default: bool | None
    repr: bool
    init_var: bool | None
    kw_only: bool | None


class _FieldInfoInputs(_FromFieldInfoInputs, total=False):
    """
    This class exists solely to add typechecking for the `**kwargs` in `FieldInfo.__init__`.
    """

    default: Any


class FieldInfo(_repr.Representation):
    """
    This class holds information about a field.

    `FieldInfo` is used for any field definition regardless of whether the `Field()` function is explicitly used.

    Attributes:
        annotation (type[Any] | None): The type annotation of the field.
        default (Any): The default value of the field.
        default_factory (Callable[[], Any] | None): The factory function used to construct the default for the field.
        alias (str | None): The alias name of the field.
        alias_priority (int | None): The priority of the field's alias.
        validation_alias (str | AliasPath | AliasChoices | None): The validation alias name of the field.
        serialization_alias (str | None): The serialization alias name of the field.
        title (str | None): The title of the field.
        description (str | None): The description of the field.
        examples (list[Any] | None): List of examples of the field.
        exclude (bool | None): Whether to exclude the field from the model schema.
        include (bool | None): Whether to include the field in the model schema.
        discriminator (str | None): Field name for discriminating the type in a tagged union.
        json_schema_extra (dict[str, Any]): Dictionary of extra JSON schema properties.
        frozen (bool | None): Whether the field is frozen.
        final (bool | None): Whether the field is final.
        validate_default (bool | None): Whether to validate the default value of the field.
        repr (bool): Whether to include the field in representation of the model.
        init_var (bool | None): Whether the field should be included in the constructor of the dataclass.
        kw_only (bool | None): Whether the field should be a keyword-only argument in the constructor of the dataclass.
        metadata (list[Any]): List of metadata constraints.
    """

    annotation: type[Any] | None
    default: Any
    default_factory: typing.Callable[[], Any] | None
    alias: str | None
    alias_priority: int | None
    validation_alias: str | AliasPath | AliasChoices | None
    serialization_alias: str | None
    title: str | None
    description: str | None
    examples: list[Any] | None
    exclude: bool | None
    include: bool | None
    discriminator: str | None
    json_schema_extra: dict[str, Any] | None
    frozen: bool | None
    final: bool | None
    validate_default: bool | None
    repr: bool
    init_var: bool | None
    kw_only: bool | None
    metadata: list[Any]

    __slots__ = (
        'annotation',
        'default',
        'default_factory',
        'alias',
        'alias_priority',
        'validation_alias',
        'serialization_alias',
        'title',
        'description',
        'examples',
        'exclude',
        'include',
        'discriminator',
        'json_schema_extra',
        'frozen',
        'final',
        'validate_default',
        'repr',
        'init_var',
        'kw_only',
        'metadata',
    )

    # used to convert kwargs to metadata/constraints,
    # None has a special meaning - these items are collected into a `PydanticGeneralMetadata`
    metadata_lookup: typing.ClassVar[dict[str, typing.Callable[[Any], Any] | None]] = {
        'strict': types.Strict,
        'gt': annotated_types.Gt,
        'ge': annotated_types.Ge,
        'lt': annotated_types.Lt,
        'le': annotated_types.Le,
        'multiple_of': annotated_types.MultipleOf,
        'min_length': annotated_types.MinLen,
        'max_length': annotated_types.MaxLen,
        'pattern': None,
        'allow_inf_nan': None,
        'max_digits': None,
        'decimal_places': None,
    }

    def __init__(self, **kwargs: typing_extensions.Unpack[_FieldInfoInputs]) -> None:
        """
        This class should generally not be initialized directly; instead, use the `pydantic.fields.Field` function
        or one of the constructor classmethods.

        See the signature of `pydantic.fields.Field` for more details about the expected arguments.
        """
        self.annotation, annotation_metadata = self._extract_metadata(kwargs.get('annotation'))

        default = kwargs.pop('default', Undefined)
        if default is Ellipsis:
            self.default = Undefined
        else:
            self.default = default

        self.default_factory = kwargs.pop('default_factory', None)

        if self.default is not Undefined and self.default_factory is not None:
            raise TypeError('cannot specify both default and default_factory')

        self.alias = kwargs.pop('alias', None)
        self.alias_priority = kwargs.pop('alias_priority', None) or 2 if self.alias is not None else None
        self.title = kwargs.pop('title', None)
        self.validation_alias = kwargs.pop('validation_alias', None)
        self.serialization_alias = kwargs.pop('serialization_alias', None)
        self.description = kwargs.pop('description', None)
        self.examples = kwargs.pop('examples', None)
        self.exclude = kwargs.pop('exclude', None)
        self.include = kwargs.pop('include', None)
        self.discriminator = kwargs.pop('discriminator', None)
        self.repr = kwargs.pop('repr', True)
        self.json_schema_extra = kwargs.pop('json_schema_extra', None)
        self.validate_default = kwargs.pop('validate_default', None)
        self.frozen = kwargs.pop('frozen', None)
        self.final = kwargs.pop('final', None)
        # currently only used on dataclasses
        self.init_var = kwargs.pop('init_var', None)
        self.kw_only = kwargs.pop('kw_only', None)

        self.metadata = self._collect_metadata(kwargs) + annotation_metadata  # type: ignore

    @classmethod
    def from_field(
        cls, default: Any = Undefined, **kwargs: typing_extensions.Unpack[_FromFieldInfoInputs]
    ) -> typing_extensions.Self:
        """
        Create a new `FieldInfo` object with the `Field` function.

        Args:
            default (Any): The default value for the field. Defaults to Undefined.
            **kwargs: Additional arguments dictionary.

        Raises:
            TypeError: If 'annotation' is passed as a keyword argument.

        Returns:
            FieldInfo: A new FieldInfo object with the given parameters.

        Examples:
            This is how you can create a field with default value like this:

            ```python
            import pydantic

            class MyModel(pydantic.BaseModel):
                foo: int = pydantic.Field(4, ...)
            ```
        """
        if 'annotation' in kwargs:
            raise TypeError('"annotation" is not permitted as a Field keyword argument')
        return cls(default=default, **kwargs)

    @classmethod
    def from_annotation(cls, annotation: type[Any]) -> typing_extensions.Self:
        """
        Creates a `FieldInfo` instance from a bare annotation.

        Args:
            annotation (type[Any]): An annotation object.

        Returns:
            FieldInfo: An instance of the field metadata.

        Examples:
            This is how you can create a field from a bare annotation like this:

            ```python
            import pydantic
            class MyModel(pydantic.BaseModel):
                foo: int  # <-- like this
            ```

            We also account for the case where the annotation can be an instance of `Annotated` and where
            one of the (not first) arguments in `Annotated` are an instance of `FieldInfo`, e.g.:

            ```python
            import pydantic, annotated_types, typing

            class MyModel(pydantic.BaseModel):
                foo: typing.Annotated[int, annotated_types.Gt(42)]
                bar: typing.Annotated[int, Field(gt=42)]
            ```

        """
        final = False
        if _typing_extra.is_finalvar(annotation):
            final = True
            if annotation is not typing_extensions.Final:
                annotation = typing_extensions.get_args(annotation)[0]

        if _typing_extra.is_annotated(annotation):
            first_arg, *extra_args = typing_extensions.get_args(annotation)
            if _typing_extra.is_finalvar(first_arg):
                final = True
            field_info = cls._find_field_info_arg(extra_args)
            if field_info:
                new_field_info = copy(field_info)
                new_field_info.annotation = first_arg
                new_field_info.final = final
                new_field_info.metadata += [a for a in extra_args if not isinstance(a, FieldInfo)]
                return new_field_info

        return cls(annotation=annotation, final=final)

    @classmethod
    def from_annotated_attribute(cls, annotation: type[Any], default: Any) -> typing_extensions.Self:
        """
        Create `FieldInfo` from an annotation with a default value.

        Args:
            annotation (type[Any]): The type annotation of the field.
            default (Any): The default value of the field.

        Returns:
            FieldInfo: A field object with the passed values.

        Examples:
        ```python
        import pydantic, annotated_types, typing

        class MyModel(pydantic.BaseModel):
            foo: int = 4  # <-- like this
            bar: typing.Annotated[int, annotated_types.Gt(4)] = 4  # <-- or this
            spam: typing.Annotated[int, pydantic.Field(gt=4)] = 4  # <-- or this
        ```
        """
        final = False
        if _typing_extra.is_finalvar(annotation):
            final = True
            if annotation is not typing_extensions.Final:
                annotation = typing_extensions.get_args(annotation)[0]

        if isinstance(default, cls):
            default.annotation, annotation_metadata = cls._extract_metadata(annotation)
            default.metadata += annotation_metadata
            default.final = final
            return default
        elif isinstance(default, dataclasses.Field):
            init_var = False
            if annotation is dataclasses.InitVar:
                if sys.version_info < (3, 8):
                    raise RuntimeError('InitVar is not supported in Python 3.7 as type information is lost')

                init_var = True
                annotation = Any
            elif isinstance(annotation, dataclasses.InitVar):
                init_var = True
                annotation = annotation.type
            pydantic_field = cls._from_dataclass_field(default)
            pydantic_field.annotation, annotation_metadata = cls._extract_metadata(annotation)
            pydantic_field.metadata += annotation_metadata
            pydantic_field.final = final
            pydantic_field.init_var = init_var
            pydantic_field.kw_only = getattr(default, 'kw_only', None)
            return pydantic_field
        else:
            if _typing_extra.is_annotated(annotation):
                first_arg, *extra_args = typing_extensions.get_args(annotation)
                field_info = cls._find_field_info_arg(extra_args)
                if field_info is not None:
                    if not field_info.is_required():
                        raise TypeError('Default may not be specified twice on the same field')
                    new_field_info = copy(field_info)
                    new_field_info.default = default
                    new_field_info.annotation = first_arg
                    new_field_info.metadata += [a for a in extra_args if not isinstance(a, FieldInfo)]
                    return new_field_info

            return cls(annotation=annotation, default=default, final=final)

    @classmethod
    def _from_dataclass_field(cls, dc_field: DataclassField[Any]) -> typing_extensions.Self:
        """
        Return a new `FieldInfo` instance from a `dataclasses.Field` instance.

        Args:
            dc_field (dataclasses.Field): The `dataclasses.Field` instance to convert.

        Returns:
            FieldInfo: The corresponding `FieldInfo` instance.

        Raises:
            TypeError: If any of the `FieldInfo` kwargs does not match the `dataclass.Field` kwargs.
        """
        default = dc_field.default
        if default is dataclasses.MISSING:
            default = Undefined

        if dc_field.default_factory is dataclasses.MISSING:
            default_factory: typing.Callable[[], Any] | None = None
        else:
            default_factory = dc_field.default_factory

        # use the `Field` function so in correct kwargs raise the correct `TypeError`
        field = Field(default=default, default_factory=default_factory, repr=dc_field.repr, **dc_field.metadata)

        field.annotation, annotation_metadata = cls._extract_metadata(dc_field.type)
        field.metadata += annotation_metadata
        return field

    @classmethod
    def _extract_metadata(cls, annotation: type[Any] | None) -> tuple[type[Any] | None, list[Any]]:
        """Tries to extract metadata/constraints from an annotation if it uses `Annotated`.

        Args:
            annotation (type[Any] | None): The type hint annotation for which metadata has to be extracted.

        Returns:
            tuple[type[Any] | None, list[Any]]: A tuple containing the extracted metadata type and the list
            of extra arguments.

        Raises:
            TypeError: If a `Field` is used twice on the same field.
        """
        if annotation is not None:
            if _typing_extra.is_annotated(annotation):
                first_arg, *extra_args = typing_extensions.get_args(annotation)
                if cls._find_field_info_arg(extra_args):
                    raise TypeError('Field may not be used twice on the same field')
                return first_arg, list(extra_args)

        return annotation, []

    @staticmethod
    def _find_field_info_arg(args: Any) -> FieldInfo | None:
        """
        Find an instance of `FieldInfo` in the provided arguments.

        Args:
            args (Any): The argument list to search for `FieldInfo`.

        Returns:
            FieldInfo | None: An instance of `FieldInfo` if found, otherwise `None`.
        """
        return next((a for a in args if isinstance(a, FieldInfo)), None)

    @classmethod
    def _collect_metadata(cls, kwargs: dict[str, Any]) -> list[Any]:
        """
        Collect annotations from kwargs.

        The return type is actually `annotated_types.BaseMetadata | PydanticMetadata`,
        but it gets combined with `list[Any]` from `Annotated[T, ...]`, hence types.

        Args:
            kwargs (dict[str, Any]): Keyword arguments passed to the function.

        Returns:
            list[Any]: A list of metadata objects - a combination of `annotated_types.BaseMetadata` and
                `PydanticMetadata`.
        """
        metadata: list[Any] = []
        general_metadata = {}
        for key, value in list(kwargs.items()):
            try:
                marker = cls.metadata_lookup[key]
            except KeyError:
                continue

            del kwargs[key]
            if value is not None:
                if marker is None:
                    general_metadata[key] = value
                else:
                    metadata.append(marker(value))
        if general_metadata:
            metadata.append(_fields.PydanticGeneralMetadata(**general_metadata))
        return metadata

    def get_default(self, *, call_default_factory: bool = False) -> Any:
        """
        Get the default value.

        We expose an option for whether to call the default_factory (if present), as calling it may
        result in side effects that we want to avoid. However, there are times when it really should
        be called (namely, when instantiating a model via `model_construct`).

        Args:
            call_default_factory (bool, optional): Whether to call the default_factory or not. Defaults to False.

        Returns:
            Any: The default value, calling the default factory if requested or `None` if not set.
        """
        if self.default_factory is None:
            return _utils.smart_deepcopy(self.default)
        elif call_default_factory:
            return self.default_factory()
        else:
            return None

    def is_required(self) -> bool:
        """Check if the argument is required.

        Returns:
            bool: `True` if the argument is required, `False` otherwise.
        """
        return self.default is Undefined and self.default_factory is None

    def rebuild_annotation(self) -> Any:
        """
        Rebuilds the original annotation for use in function signatures.

        If metadata is present, it adds it to the original annotation using an
        `AnnotatedAlias`. Otherwise, it returns the original annotation as is.

        Returns:
            Any: The rebuilt annotation.
        """
        if not self.metadata:
            return self.annotation
        else:
            return typing_extensions._AnnotatedAlias(self.annotation, self.metadata)

    def apply_typevars_map(self, typevars_map: dict[Any, Any] | None, types_namespace: dict[str, Any] | None) -> None:
        """
        Apply a `typevars_map` to the annotation.

        This method is used when analyzing parametrized generic types to replace typevars with their concrete types.

        Args:
            typevars_map (dict | None): A dictionary mapping type variables to their concrete types.
            types_namespace (dict | None): A dictionary containing related types to the annotated type.

        Returns:
            None. This method applies the `typevars_map` to the annotation in place.

        See Also:
            pydantic._internal._generics.replace_types: This function is used for replacing the typevars with
                their concrete types.
        """
        annotation = _typing_extra.eval_type_lenient(self.annotation, types_namespace, None)
        self.annotation = replace_types(annotation, typevars_map)

    def __repr_args__(self) -> ReprArgs:
        yield 'annotation', _repr.PlainRepr(_repr.display_as_type(self.annotation))
        yield 'required', self.is_required()

        for s in self.__slots__:
            if s == 'annotation':
                continue
            elif s == 'metadata' and not self.metadata:
                continue
            elif s == 'repr' and self.repr is True:
                continue
            elif s == 'final':
                continue
            if s == 'frozen' and self.frozen is False:
                continue
            if s == 'validation_alias' and self.validation_alias == self.alias:
                continue
            if s == 'serialization_alias' and self.serialization_alias == self.alias:
                continue
            if s == 'default_factory' and self.default_factory is not None:
                yield 'default_factory', _repr.PlainRepr(_repr.display_as_type(self.default_factory))
            else:
                value = getattr(self, s)
                if value is not None and value is not Undefined:
                    yield s, value


@_internal_dataclass.slots_dataclass
class AliasPath:
    """
    A data class used by `validation_alias` as a convenience to create aliases.

    Attributes:
        path (list[int | str]): A list of string or integer aliases.

    Methods:
        convert_to_aliases(self) -> list[str | int]: Converts arguments to a list of string or integer aliases.
    """

    path: list[int | str]

    def __init__(self, first_arg: str, *args: str | int) -> None:
        self.path = [first_arg] + list(args)

    def convert_to_aliases(self) -> list[str | int]:
        """
        Converts arguments to a list of string or integer aliases.

        Returns:
            list[str | int]: The list of aliases.
        """
        return self.path


@_internal_dataclass.slots_dataclass
class AliasChoices:
    """
    A data class used by `validation_alias` as a convenience to create aliases.

    Attributes:
        path (list[str | AliasPatch]): A list containing string or AliasPath.

    Methods:
        convert_to_aliases(self) -> list[str | int]: Converts arguments to a list of lists containing string or
            integer aliases.
    """

    choices: list[str | AliasPath]

    def __init__(self, first_choice: str | AliasPath, *choices: str | AliasPath) -> None:
        self.choices = [first_choice] + list(choices)

    def convert_to_aliases(self) -> list[list[str | int]]:
        """
        Converts arguments to a list of lists containing string or integer aliases.

        Returns:
            list[list[str | int]]: The list of aliases.
        """
        aliases: list[list[str | int]] = []
        for c in self.choices:
            if isinstance(c, AliasPath):
                aliases.append(c.convert_to_aliases())
            else:
                aliases.append([c])
        return aliases


class _EmptyKwargs(typing_extensions.TypedDict):
    """
    This class exists solely to ensure that typechecking warns about passing `**extra` in `Field`
    """

    pass


def Field(  # noqa C901
    default: Any = Undefined,
    *,
    default_factory: typing.Callable[[], Any] | None = None,
    alias: str | None = None,
    alias_priority: int | None = None,
    validation_alias: str | AliasPath | AliasChoices | None = None,
    serialization_alias: str | None = None,
    title: str | None = None,
    description: str | None = None,
    examples: list[Any] | None = None,
    exclude: bool | None = None,
    include: bool | None = None,
    discriminator: str | None = None,
    json_schema_extra: dict[str, Any] | None = None,
    frozen: bool | None = None,
    final: bool | None = None,
    validate_default: bool | None = None,
    repr: bool = True,
    init_var: bool | None = None,
    kw_only: bool | None = None,
    pattern: str | None = None,
    strict: bool | None = None,
    gt: float | None = None,
    ge: float | None = None,
    lt: float | None = None,
    le: float | None = None,
    multiple_of: float | None = None,
    allow_inf_nan: bool | None = None,
    max_digits: int | None = None,
    decimal_places: int | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    **extra: typing_extensions.Unpack[_EmptyKwargs],
) -> Any:
    """
    Create a field for objects that can be configured.

    Used to provide extra information about a field, either for the model schema or complex validation. Some arguments
    apply only to number fields (`int`, `float`, `Decimal`) and some apply only to `str`.

    Args:
        default (Any, optional): default value if the field is not set.
        default_factory (Callable[[], Any] | None, optional): A callable to generate the default value,
            such as :func:`~datetime.utcnow`.
        alias (str | None, optional): an alternative name for the attribute.
        alias_priority (int | None, optional): priority of the alias. This affects whether an alias generator is used
        validation_alias (str | AliasPath | AliasChoices | None, optional): 'whitelist' validation step. The field
            will be the single one allowed by the alias or set of aliases defined.
        serialization_alias (str | None, optional): 'blacklist' validation step. The vanilla field will be the single
            one of the alias' or set of aliases' fields and all the other fields will be ignored at serialization time.
        title (str | None, optional): human-readable title.
        description (str | None, optional): human-readable description.
        examples (list[Any] | None, optional): Example values for this field.
        exclude (bool | None): Whether to exclude the field from the model schema.
        include (bool | None): Whether to include the field in the model schema.
        discriminator (str | None): Field name for discriminating the type in a tagged union.
        json_schema_extra (dict[str, Any] | None, optional): Any additional JSON schema data for the schema property.
        frozen (bool | None, optional): Whether the field is frozen.
        final (bool | None, optional): Whether the field is final.
        validate_default (bool | None, optional): Run validation that isn't only checking existence of defaults. This is
            `True` by default.
        repr (bool, optional): If `True` (the default), return a string representation of the field.
        init_var (bool | None, optional): Whether the field should be included in the constructor of the dataclass.
        kw_only (bool | None, optional): Whether the field should be a keyword-only argument in the constructor
            of the dataclass.
        strict (bool | None, optional): If `True` (the default is `None`), the field should be validated strictly.
        gt (float | None, optional): Greater than. If set, value must be greater than this. Only applicable to numbers.
        ge (float | None, optional): Greater than or equal. If set, value must be
            greater than or equal to this. Only applicable to numbers.
        lt (float | None, optional): Less than. If set, value must be
            less than this. Only applicable to numbers.
        le (float | None, optional): Less than or equal. If set, value must be
            less than or equal to this. Only applicable to numbers.
        multiple_of (float | None, optional): Value must be a multiple of this. Only applicable to numbers.
        min_length (int | None, optional): Minimum length for strings.
        max_length (int | None, optional): Maximum length for strings.
        pattern (str | None, optional): Pattern for strings.
        allow_inf_nan (bool | None, optional): Allow `inf`, `-inf`, `nan`. Only applicable to numbers.
        max_digits (int | None, optional): Maximum number of allow digits for strings.
        decimal_places (int | None, optional): Maximum number decimal places allowed for numbers.

    Returns:
        FieldInfo: the generated FieldInfo object
    """
    # Check deprecated and removed params from V1. This logic should eventually be removed.
    const = extra.pop('const', None)  # type: ignore
    if const is not None:
        raise PydanticUserError('`const` is removed, use `Literal` instead', code='deprecated-kwargs')

    min_items = extra.pop('min_items', None)  # type: ignore
    if min_items is not None:
        warn('`min_items` is deprecated and will be removed, use `min_length` instead', DeprecationWarning)
        if min_length is None:
            min_length = min_items  # type: ignore

    max_items = extra.pop('max_items', None)  # type: ignore
    if max_items is not None:
        warn('`max_items` is deprecated and will be removed, use `max_length` instead', DeprecationWarning)
        if max_length is None:
            max_length = max_items  # type: ignore

    unique_items = extra.pop('unique_items', None)  # type: ignore
    if unique_items is not None:
        raise PydanticUserError(
            (
                '`unique_items` is removed, use `Set` instead'
                '(this feature is discussed in https://github.com/pydantic/pydantic-core/issues/296)'
            ),
            code='deprecated-kwargs',
        )

    allow_mutation = extra.pop('allow_mutation', None)  # type: ignore
    if allow_mutation is not None:
        warn('`allow_mutation` is deprecated and will be removed. use `frozen` instead', DeprecationWarning)
        if allow_mutation is False:
            frozen = True

    regex = extra.pop('regex', None)  # type: ignore
    if regex is not None:
        raise PydanticUserError('`regex` is removed. use `pattern` instead', code='deprecated-kwargs')

    if extra:
        warn(
            'Extra keyword arguments on `Field` is deprecated and will be removed. use `json_schema_extra` instead',
            DeprecationWarning,
        )
        if not json_schema_extra:
            json_schema_extra = extra  # type: ignore

    if validation_alias:
        if not isinstance(validation_alias, (str, AliasChoices, AliasPath)):
            raise TypeError('Invalid `validation_alias` type. it should be `str`, `AliasChoices`, or `AliasPath`')

    if serialization_alias is None and isinstance(alias, str):
        serialization_alias = alias

    return FieldInfo.from_field(
        default,
        default_factory=default_factory,
        alias=alias,
        alias_priority=alias_priority,
        validation_alias=validation_alias or alias,
        serialization_alias=serialization_alias,
        title=title,
        description=description,
        examples=examples,
        exclude=exclude,
        include=include,
        discriminator=discriminator,
        json_schema_extra=json_schema_extra,
        frozen=frozen,
        final=final,
        pattern=pattern,
        validate_default=validate_default,
        repr=repr,
        init_var=init_var,
        kw_only=kw_only,
        strict=strict,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        multiple_of=multiple_of,
        min_length=min_length,
        max_length=max_length,
        allow_inf_nan=allow_inf_nan,
        max_digits=max_digits,
        decimal_places=decimal_places,
    )


class ModelPrivateAttr(_repr.Representation):
    """A descriptor for private attributes in class models.

    Attributes:
        default (Any): The default value of the attribute if not provided.
        default_factory (typing.Callable[[], Any]): A callable function that generates the default value of the
            attribute if not provided.
    """

    __slots__ = 'default', 'default_factory'

    def __init__(self, default: Any = Undefined, *, default_factory: typing.Callable[[], Any] | None = None) -> None:
        self.default = default
        self.default_factory = default_factory

    def __set_name__(self, cls: type[Any], name: str) -> None:
        """
        preserve `__set_name__` protocol defined in https://peps.python.org/pep-0487
        """
        if self.default is Undefined:
            return
        if not hasattr(self.default, '__set_name__'):
            return
        set_name = self.default.__set_name__
        if callable(set_name):
            set_name(cls, name)

    def get_default(self) -> Any:
        """Returns the default value for the object.

        If `self.default_factory` is `None`, the method will return a deep copy of the `self.default` object.
        If `self.default_factory` is not `None`, it will call `self.default_factory` and return the value returned.

        Returns:
            Any: The default value of the object.
        """
        return _utils.smart_deepcopy(self.default) if self.default_factory is None else self.default_factory()

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, self.__class__) and (self.default, self.default_factory) == (
            other.default,
            other.default_factory,
        )


def PrivateAttr(
    default: Any = Undefined,
    *,
    default_factory: typing.Callable[[], Any] | None = None,
) -> Any:
    """
    Indicates that attribute is only used internally and never mixed with regular fields.

    Private attributes are not checked by Pydantic, so it's up to you to maintain their accuracy.

    Private attributes are stored in the model `__slots__`.

    Args:
        default (Any): The attribute's default value. Defaults to Undefined.
        default_factory (typing.Callable[[], Any], optional): Callable that will be
            called when a default value is needed for this attribute.
            If both `default` and `default_factory` are set, an error will be raised.

    Returns:
        Any: An instance of `ModelPrivateAttr` class.

    Raises:
        ValueError: If both `default` and `default_factory` are set.
    """
    if default is not Undefined and default_factory is not None:
        raise TypeError('cannot specify both default and default_factory')

    return ModelPrivateAttr(
        default,
        default_factory=default_factory,
    )


@_internal_dataclass.slots_dataclass
class ComputedFieldInfo:
    """
    A container for data from `@computed_field` so that we can access it while building the pydantic-core schema.

    Attributes:
        decorator_repr (typing.ClassVar[str]): A class variable representing the decorator string, '@computed_field'.
        wrapped_property (property): The wrapped computed field property.
        return_type (type[Any]): The type of the computed field property's return value.
        alias (str|None): The alias of the property to be used during encoding and decoding.
        alias_priority (int|None): priority of the alias. This affects whether an alias generator is used
        title (str|None): Title of the computed field as in OpenAPI document, should be a short summary.
        description (str|None): Description of the computed field as in OpenAPI document.
        repr (bool): A boolean indicating whether or not to include the field in the __repr__ output.
    """

    decorator_repr: typing.ClassVar[str] = '@computed_field'
    wrapped_property: property
    return_type: type[Any]
    alias: str | None
    alias_priority: int | None
    title: str | None
    description: str | None
    repr: bool


# this should really be `property[T], cached_proprety[T]` but property is not generic unlike cached_property
# See https://github.com/python/typing/issues/985 and linked issues
PropertyT = typing.TypeVar('PropertyT')
"""
`TypeVar` that can be used to specify the type of a property.

This can be used in combination with the `@property` decorator to specify the type
of the property.

Example:
    ```py
    class MyClass:
        @property
        def my_property(self) -> PropertyT:
            return self._my_property

        @my_property.setter
        def my_property(self, value: PropertyT) -> None:
            self._my_property = value
    ```
"""


@typing.overload
def computed_field(
    *,
    return_type: Any = Any,
    alias: str | None = None,
    alias_priority: int | None = None,
    title: str | None = None,
    description: str | None = None,
    repr: bool = True,
) -> typing.Callable[[PropertyT], PropertyT]:
    ...


@typing.overload
def computed_field(__func: PropertyT) -> PropertyT:
    ...


_UNSET: Any = object()


def computed_field(
    __f: PropertyT | None = None,
    *,
    alias: str | None = None,
    alias_priority: int | None = None,
    title: str | None = None,
    description: str | None = None,
    repr: bool = True,
    return_type: Any = _UNSET,
) -> PropertyT | typing.Callable[[PropertyT], PropertyT]:
    """
    Decorate to include `property` and `cached_property` when serialising models.

    If applied to functions not yet decorated with `@property` or `@cached_property`, the function is
    automatically wrapped with `property`.

    Args:
        __f: the function to wrap.
        alias: alias to use when serializing this computed field, only used when `by_alias=True`
        alias_priority: priority of the alias. This affects whether an alias generator is used
        title: Title to used when including this computed field in JSON Schema, currently unused waiting for #4697
        description: Description to used when including this computed field in JSON Schema, defaults to the functions
            docstring, currently unused waiting for #4697
        repr: whether to include this computed field in model repr
        return_type: optional return for serialization logic to expect when serialising to JSON, if included
            this must be correct, otherwise a `TypeError` is raised.
            If you don't include a return type Any is used, which does runtime introspection to handle arbitrary
            objects.

    Returns:
        A proxy wrapper for the property.
    """

    def dec(f: Any) -> Any:
        nonlocal description, return_type, alias_priority
        if description is None and f.__doc__:
            description = inspect.cleandoc(f.__doc__)

        if return_type is _UNSET:
            # try to get it from the type annotation
            res = _typing_extra.get_type_hints(_decorators.unwrap_wrapped_function(f), include_extras=True)
            return_type = res.get('return', _UNSET)
            if return_type is _UNSET:
                raise PydanticUserError(
                    'Computed field is missing return type annotation or specifying `return_type`'
                    ' to the `@computed_field` decorator (e.g. `@computed_field(return_type=int|str)`)',
                    code='model-field-missing-annotation',
                )

        # if the function isn't already decorated with `@property` (or another descriptor), then we wrap it now
        f = _decorators.ensure_property(f)
        alias_priority = (alias_priority or 2) if alias is not None else None
        dec_info = ComputedFieldInfo(f, return_type, alias, alias_priority, title, description, repr)
        return _decorators.PydanticDescriptorProxy(f, dec_info)

    if __f is None:
        return dec
    else:
        return dec(__f)
