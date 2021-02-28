from django.template import Context, Template
from django.conf import settings

__all__ = ('TemplateHintProvider', 'CompositeTemplateHintProvider',
           'TemplateNameProvider', 'Renderable',)


class TemplateHintProvider(object):
    '''
    Use this mixin for objects which shall provide template hints.
    '''

    def get_template_hints(self, name_provider, hint_providers):
        '''
        Return a list of strings that indicate hints that should be appended
        to the object's standard template name. For example if you provide the
        hints ``['fancy', 'lame']``, the following templates might be searched
        for to render the object::

            app/modelname_fancy.html
            app/modelname_lame.html
            app/modelname.html

        Override this method in subclasses.
        '''
        return []

    def suggest_context_data(self, name_provider, hint_providers):
        '''
        Return a dict which will be injected into the context of the to be
        rendered object. This is usefull to pass in data from a parent object
        into the child elements, e.g. data from a gallery that should be
        available in the template for the image.
        '''
        return {}

    def suggest_template_names(self, name_provider, hint_providers, **kwargs):
        '''
        Use the hints generated by ``get_template_hints`` to compile a list of
        possible template names that shall be searched to render the given
        ``obj``. ``obj`` must provide a ``get_template_name`` (e.g. is an
        instance of ``Renderable``) which takes a hint as an argument and
        returns the hinted template name.
        '''
        template_names = []
        for hint in self.get_template_hints(name_provider, hint_providers):
            if hint:
                template_names.append(
                    name_provider.get_template_name(
                        hint=hint,
                        **kwargs))
        return template_names


class CompositeTemplateHintProvider(list):
    '''
    Can be used as a composite of multiple TemplateHintProviders. That's
    useful if you want to group the providers into a list. It's used for
    example in the ``{% render_content %}`` template tag.
    '''

    def get_template_hints(self, name_provider, hint_providers=None):
        if hint_providers is None:
            hint_providers = self
        template_hints = []
        for hint_provider in hint_providers:
            template_hints.extend(
                hint_provider.get_template_hints(name_provider, hint_providers))
        return template_hints

    def suggest_context_data(self, name_provider, hint_providers=None):
        if hint_providers is None:
            hint_providers = self
        context_data = {}
        for hint_provider in hint_providers:
            context_data.update(
                hint_provider.suggest_context_data(name_provider, hint_providers))
        return context_data

    def suggest_template_names(self, name_provider, hint_providers=None, **kwargs):
        if hint_providers is None:
            hint_providers = self
        template_names = []
        for hint_provider in hint_providers:
            template_names.extend(
                hint_provider.suggest_template_names(
                    name_provider,
                    hint_providers=hint_providers,
                    **kwargs))
        return template_names


class TemplateNameProvider(object):
    '''
    A TemplateNameProvider is any class that may provide template names
    based on multiple template hints. This is primarily used for Renderable objects
    (see below), but may be used inside other objects, too.
    '''

    template_name = '{{app_label}}/' \
                    '{%if partial or type == "partial"%}_{%endif%}' \
                    '{{object_name}}' \
                    '{%if type != "partial"%}_{{type}}{%endif%}' \
                    '{%if hint%}_{{hint}}{%endif%}' \
                    '.html'

    def get_app_label(self):
        return self._meta.app_label.lower()

    def get_model_name(self):
        return self._meta.object_name.lower()

    def get_template_name(self, template_name=None, **kwargs):
        '''
        Return the template name for this object. By overriding this method in
        subclasses, you have complete control of where how the template name
        for the model is determined. You are also free to incorporate the hint
        into the directory structure.

        In the default implementation the class attribute ``template_name`` is
        itself used as a template to generate the template name from a few
        variables. You can use the following variables:

        ``app_label``:
            The name of the app the model lives in.
        ``object_name``:
            The model's class name, in lower case.
        ``object``:
            The renderable itself.

        Additionally to the listed variables above are all keyword arguments
        passed to ``get_template_name`` available.

        To get to a common set of variables that you can rely on to built a
        sophisticated template name, you should always provide the ``type``
        and ``hint`` parameters when calling ``get_template_name``.

        The ``type`` differentiates in which context the object is beeing
        rendered. It can be for example ``'detail'`` which will render a whole
        HTML page, or you can specify ``'partial'`` to render the object only
        as widget inside a wrapping page.

        The ``hint`` is a template hint given by a used TemplateHintProvider.
        '''
        if template_name is None:
            template_name = self.template_name

        context = {
            'app_label': self.get_app_label(),
            'object_name': self.get_model_name(),
            'object': self,
        }
        context.update(kwargs)
        template = Template(template_name)
        return template.render(Context(context))


    def get_template_names(self, hint_providers, **kwargs):
        '''
        Compile a list of template names for which the first existing one
        shall be used to render the object. You can provide a list of
        ``TemplateHintProvider``s that will be taken into account.

        All extra keyword arguments will be passed down to
        ``get_template_name``.
        '''
        template_names = []
        for hint_provider in hint_providers:
            template_names.extend(
                hint_provider.suggest_template_names(
                    self,
                    hint_providers=hint_providers,
                    **kwargs))
        # Add a template name without a hint as a fallback.
        template_names.append(
            self.get_template_name(**kwargs))
        return template_names


class Renderable(TemplateNameProvider):
    '''
    Use this as an mixin for objects that shall be renderable in the template
    via the ``{% render_content %}`` template tag. Renderable objects can
    provide the path to the template and the context data that should be used
    to render the object.
    '''

    context_object_name = None

    def get_context_object_name(self):
        if self.context_object_name:
            return self.context_object_name
        return self.get_model_name()

    def get_context_data(self, **kwargs):
        '''
        Give the context that shall be used to render the object's template.
        '''
        return {
            self.get_context_object_name(): self,
            'object': self,
        }
