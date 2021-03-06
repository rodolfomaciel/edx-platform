"""
Tests for generate_course_blocks management command.
"""
import ddt
from django.core.management.base import CommandError
import itertools
from mock import patch

from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from .. import generate_course_blocks
from openedx.core.djangoapps.content.block_structure.tests.helpers import is_course_in_block_structure_cache


@ddt.ddt
class TestGenerateCourseBlocks(ModuleStoreTestCase):
    """
    Tests generate course blocks management command.
    """
    num_courses = 2

    def setUp(self):
        """
        Create courses in modulestore.
        """
        super(TestGenerateCourseBlocks, self).setUp()
        self.courses = [CourseFactory.create() for _ in range(self.num_courses)]
        self.course_keys = [course.id for course in self.courses]
        self.command = generate_course_blocks.Command()

    def _assert_courses_not_in_block_cache(self, *course_keys):
        """
        Assert courses don't exist in the course block cache.
        """
        for course_key in course_keys:
            self.assertFalse(is_course_in_block_structure_cache(course_key, self.store))

    def _assert_courses_in_block_cache(self, *course_keys):
        """
        Assert courses exist in course block cache.
        """
        for course_key in course_keys:
            self.assertTrue(is_course_in_block_structure_cache(course_key, self.store))

    def _assert_message_presence_in_logs(self, message, mock_log, expected_presence=True):
        """
        Asserts that the logger was called with the given message.
        """
        message_present = any([message in call_args[0][0] for call_args in mock_log.warning.call_args_list])
        if expected_presence:
            self.assertTrue(message_present)
        else:
            self.assertFalse(message_present)

    @ddt.data(True, False)
    def test_all_courses(self, force_update):
        self._assert_courses_not_in_block_cache(*self.course_keys)
        self.command.handle(all_courses=True)
        self._assert_courses_in_block_cache(*self.course_keys)
        with patch(
            'openedx.core.lib.block_structure.factory.BlockStructureFactory.create_from_modulestore'
        ) as mock_update_from_store:
            self.command.handle(all_courses=True, force_update=force_update)
            self.assertEqual(mock_update_from_store.call_count, self.num_courses if force_update else 0)

    def test_one_course(self):
        self._assert_courses_not_in_block_cache(*self.course_keys)
        self.command.handle(courses=[unicode(self.course_keys[0])])
        self._assert_courses_in_block_cache(self.course_keys[0])
        self._assert_courses_not_in_block_cache(*self.course_keys[1:])

    @ddt.data(
        *itertools.product(
            (True, False),
            (True, False),
            ('route_1', None),
        )
    )
    @ddt.unpack
    def test_enqueue(self, enqueue_task, force_update, routing_key):
        command_options = dict(all_courses=True, enqueue_task=enqueue_task, force_update=force_update)
        if enqueue_task and routing_key:
            command_options['routing_key'] = routing_key

        with patch(
            'lms.djangoapps.course_blocks.management.commands.generate_course_blocks.tasks'
        ) as mock_tasks:
            with patch(
                'lms.djangoapps.course_blocks.management.commands.generate_course_blocks.api'
            ) as mock_api:

                self.command.handle(**command_options)

                self.assertEqual(
                    mock_tasks.update_course_in_cache.apply_async.call_count,
                    self.num_courses if enqueue_task and force_update else 0,
                )
                self.assertEqual(
                    mock_tasks.get_course_in_cache.apply_async.call_count,
                    self.num_courses if enqueue_task and not force_update else 0,
                )

                self.assertEqual(
                    mock_api.update_course_in_cache.call_count,
                    self.num_courses if not enqueue_task and force_update else 0,
                )
                self.assertEqual(
                    mock_api.get_course_in_cache.call_count,
                    self.num_courses if not enqueue_task and not force_update else 0,
                )

                if enqueue_task:
                    task_action = mock_tasks.update_course_in_cache if force_update else mock_tasks.get_course_in_cache
                    task_options = task_action.apply_async.call_args[1]
                    if routing_key:
                        self.assertEquals(task_options['routing_key'], routing_key)
                    else:
                        self.assertNotIn('routing_key', task_options)

    @patch('lms.djangoapps.course_blocks.management.commands.generate_course_blocks.log')
    def test_not_found_key(self, mock_log):
        self.command.handle(courses=['fake/course/id'])
        self.assertTrue(mock_log.exception.called)

    def test_invalid_key(self):
        with self.assertRaises(CommandError):
            self.command.handle(courses=['not/found'])

    def test_no_params(self):
        with self.assertRaises(CommandError):
            self.command.handle(all_courses=False)

    def test_no_course_mode(self):
        with self.assertRaisesMessage(CommandError, 'Either --courses or --all_courses must be specified.'):
            self.command.handle()

    def test_both_course_modes(self):
        with self.assertRaisesMessage(CommandError, 'Both --courses and --all_courses cannot be specified.'):
            self.command.handle(all_courses=True, courses=['some/course/key'])

    @ddt.data(
        ('routing_key', 'enqueue_task'),
        ('start_index', 'all_courses'),
        ('end_index', 'all_courses'),
    )
    @ddt.unpack
    def test_dependent_options_error(self, dependent_option, depending_on_option):
        expected_error_message = 'Option --{} requires option --{}.'.format(dependent_option, depending_on_option)
        options = {dependent_option: 1, depending_on_option: False, 'courses': ['some/course/key']}
        with self.assertRaisesMessage(CommandError, expected_error_message):
            self.command.handle(**options)
