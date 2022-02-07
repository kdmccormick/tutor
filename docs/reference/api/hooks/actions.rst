.. _actions:

=======
Actions
=======

Actions are one of the two types of hooks (with :ref:`filters`) that can be used to extend Tutor. Actions are function callbacks that are called at various points during the application life cycle. Each action has a name, and callback functions can be attached to it. These functions are called in sequence and each can trigger side effects, independently from one another.

.. autofunction:: tutor.hooks.actions::get
.. autofunction:: tutor.hooks.actions::get_template
.. autofunction:: tutor.hooks.actions::add
.. autofunction:: tutor.hooks.actions::do
.. autofunction:: tutor.hooks.actions::clear
.. autofunction:: tutor.hooks.actions::clear_all

.. autoclass:: tutor.hooks.actions.Action
.. autoclass:: tutor.hooks.actions.ActionTemplate
