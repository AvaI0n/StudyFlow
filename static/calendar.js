
document.addEventListener('DOMContentLoaded', () => {
    const $ = id => document.getElementById(id);

    let assignments = [];
    let commitments = [];
    let sessions = [];

    const PAGE_SIZE = 35;
    let assignmentLimit = PAGE_SIZE;
    let commitmentLimit = PAGE_SIZE;
    let sessionLimit = PAGE_SIZE;

    const notice = message => {
        $('notice').textContent = message;
    };

    async function api(path, method = 'GET', data) {
        const response = await fetch(path, {
            method,
            headers: {
                'Content-Type': 'application/json'
            },
            ...(data === undefined ? {} : {
                body: JSON.stringify(data)
            })
        });

        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw Error(
                result.error || `Request failed (${response.status})`
            );
        }

        return result;
    }

    function button(label, action, className = '') {
        const element = document.createElement('button');
        element.type = 'button';
        element.textContent = label;

        if (className) {
            element.className = className;
        }

        element.addEventListener('click', action);
        return element;
    }

    function createItem(title, description) {
        const element = document.createElement('div');
        element.className = 'item';

        const heading = document.createElement('strong');
        heading.textContent = title;

        const small = document.createElement('small');
        small.textContent = description;

        const actions = document.createElement('div');
        actions.className = 'actions';

        element.append(heading, small, actions);

        return { element, actions };
    }

    function isExpanded(element) {
        const details = element.closest('details');
        return !details || details.open;
    }

    // Search and pagination controls.
    // These are added automatically without changing index.html.

    function makeListControls(
        listId,
        placeholder,
        onFilter,
        onMore,
        moreText
    ) {
        const list = $(listId);

        const controls = document.createElement('div');
        controls.className = 'actions';
        controls.style.marginBottom = '12px';

        const search = document.createElement('input');
        search.type = 'search';
        search.placeholder = placeholder;
        search.setAttribute('aria-label', placeholder);
        search.style.flex = '1 1 190px';
        search.style.minWidth = '0';

        search.addEventListener('input', onFilter);

        controls.append(search);
        list.before(controls);

        const count = document.createElement('p');
        count.className = 'hint';
        count.setAttribute('aria-live', 'polite');

        controls.after(count);

        const more = button(moreText, onMore);
        more.style.marginTop = '10px';
        more.hidden = true;

        list.after(more);

        return {
            search,
            count,
            more,
            controls
        };
    }

    // ASSIGNMENT SEARCH

    const assignmentUI = makeListControls(
        'assignmentList',
        'Search assignments or courses...',
        () => {
            assignmentLimit = PAGE_SIZE;
            renderAssignments();
        },
        () => {
            assignmentLimit += PAGE_SIZE;
            renderAssignments();
        },
        'Show more assignments'
    );

    const statusFilter = document.createElement('select');

    statusFilter.setAttribute(
        'aria-label',
        'Filter assignment status'
    );

    statusFilter.innerHTML = [
        '<option value="all">All assignments</option>',
        '<option value="open">Not completed</option>',
        '<option value="completed">Completed</option>'
    ].join('');

    statusFilter.addEventListener('change', () => {
        assignmentLimit = PAGE_SIZE;
        renderAssignments();
    });

    assignmentUI.controls.append(statusFilter);

    // COMMITMENT SEARCH

    const commitmentUI = makeListControls(
        'commitmentList',
        'Search commitments...',
        () => {
            commitmentLimit = PAGE_SIZE;
            renderCommitments();
        },
        () => {
            commitmentLimit += PAGE_SIZE;
            renderCommitments();
        },
        'Show more commitments'
    );

    // STUDY SESSION SEARCH

    const sessionUI = makeListControls(
        'sessionList',
        'Search proposed study sessions...',
        () => {
            sessionLimit = PAGE_SIZE;
            renderSessions();
        },
        () => {
            sessionLimit += PAGE_SIZE;
            renderSessions();
        },
        'Show more sessions'
    );

    // CALENDAR OPTIMIZATION
    // Only create events for the currently visible calendar range.

    function eventsForRange(fetchInfo) {
        const rangeStart = fetchInfo.startStr.slice(0, 10);
        const rangeEnd = fetchInfo.endStr.slice(0, 10);

        const startMilliseconds = fetchInfo.start.getTime();
        const endMilliseconds = fetchInfo.end.getTime();

        const events = [];

        // ASSIGNMENT EVENTS

        for (const a of assignments) {
            const due = (a.due_date || '').slice(0, 10);

            if (!due || due < rangeStart || due >= rangeEnd) {
                continue;
            }

            events.push({
                id: 'assignment-' + a.id,
                title: a.title,
                start: due,
                allDay: true,
                color: a.completed
                    ? '#8da0bc'
                    : '#314f91'
            });
        }

        // COMMITMENT EVENTS

        const colors = {
            Work: '#c64045',
            Class: '#168759',
            Personal: '#9157bb',
            Study: '#e1943a',
            Google: '#546577'
        };

        for (const c of commitments) {
            if (!c.date) continue;

            const color = c.flexibility === 'Free'
                ? '#acb4c0'
                : (colors[c.type] || '#52657b');

            const event = {
                id: 'commitment-' + c.id,
                title: c.title,
                color
            };

            if (c.repeat_weekly) {
                if (c.date >= rangeEnd) continue;

                const weekday = new Date(
                    c.date + 'T12:00:00'
                ).getDay();

                if (Number.isNaN(weekday)) continue;

                Object.assign(event, {
                    daysOfWeek: [weekday],
                    startTime: c.start_time,
                    endTime: c.end_time,
                    startRecur: c.date > rangeStart
                        ? c.date
                        : rangeStart,
                    endRecur: rangeEnd
                });

            } else {
                if (
                    c.date < rangeStart ||
                    c.date >= rangeEnd
                ) {
                    continue;
                }

                Object.assign(event, {
                    start: c.date + 'T' + c.start_time,
                    end: c.date + 'T' + c.end_time
                });
            }

            events.push(event);
        }

        // STUDY SESSION EVENTS

        for (const s of sessions) {
            const start = new Date(s.starts).getTime();
            const end = new Date(s.ends).getTime();

            if (
                !Number.isFinite(start) ||
                !Number.isFinite(end)
            ) {
                continue;
            }

            if (
                start >= endMilliseconds ||
                end <= startMilliseconds
            ) {
                continue;
            }

            events.push({
                id: 'session-' + s.id,
                title: s.title + ' (' + s.status + ')',
                start: s.starts,
                end: s.ends,
                color: s.status === 'approved'
                    ? '#7940ac'
                    : '#9da5b4'
            });
        }

        return events;
    }

    // FULLCALENDAR

    const calendar = new FullCalendar.Calendar(
        $('studyCalendar'),
        {
            initialView: 'dayGridMonth',
            height: 520,
            nowIndicator: true,

            // Busy days show "+ more" instead of expanding.
            dayMaxEvents: 3,

            lazyFetching: true,

            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay'
            },

            events: (
                info,
                successCallback,
                failureCallback
            ) => {
                try {
                    successCallback(eventsForRange(info));
                } catch (error) {
                    failureCallback(error);
                }
            },

            dateClick: info => {
                $('dueDate').value =
                    info.dateStr.slice(0, 10);

                // Open the assignment form automatically.
                const details = $('assignmentForm')
                    .closest('details');

                if (details) {
                    details.open = true;
                }

                $('assignmentName').focus();
            },

            eventClick: info => {
                notice(
                    info.event.title +
                    ' — Manage this event from its list below.'
                );
            }
        }
    );

    calendar.render();

    function renderCalendar() {
        // Refresh current calendar view in one operation.
        calendar.refetchEvents();
    }

    // RENDER ASSIGNMENTS

    function renderAssignments() {
        const list = $('assignmentList');

        const query = assignmentUI.search.value
            .trim()
            .toLowerCase();

        const status = statusFilter.value;

        const filtered = assignments.filter(a => {
            if (
                status === 'open' &&
                a.completed
            ) {
                return false;
            }

            if (
                status === 'completed' &&
                !a.completed
            ) {
                return false;
            }

            return !query ||
                (a.title || '')
                    .toLowerCase()
                    .includes(query) ||
                (a.course || '')
                    .toLowerCase()
                    .includes(query);
        });

        filtered.sort((a, b) =>
            (a.due_date || '').localeCompare(
                b.due_date || ''
            )
        );

        const visible = filtered.slice(
            0,
            assignmentLimit
        );

        const fragment = document.createDocumentFragment();

        for (const a of visible) {
            const { element, actions } = createItem(
                a.title,
                `${a.course || 'No course'} · ` +
                `Due ${a.due_date} · ` +
                `${a.difficulty || 'Unrated'} · ` +
                `${a.estimated_hours || '?'} hours` +
                (a.completed ? ' · Completed' : '')
            );

            // COMPLETE / UNCOMPLETE

            actions.append(
                button(
                    a.completed
                        ? 'Undo Complete'
                        : 'Mark Complete',
                    async () => {
                        try {
                            await api(
                                '/api/assignments/' +
                                encodeURIComponent(a.id),
                                'PATCH',
                                {
                                    completed: !a.completed
                                }
                            );

                            await reload();

                        } catch (error) {
                            alert(error.message);
                        }
                    }
                )
            );

            // AI ESTIMATE

            actions.append(
                button('AI Estimate', async () => {
                    try {
                        notice(
                            'AI is estimating the assignment...'
                        );

                        const result = await api(
                            '/api/estimate/' +
                            encodeURIComponent(a.id),
                            'POST'
                        );

                        await reload();

                        notice(
                            `AI estimated ${result.difficulty}, ` +
                            `${result.estimated_hours} hours. ` +
                            'You can edit this.'
                        );

                    } catch (error) {
                        alert(error.message);
                    }
                })
            );

            // AI SUGGEST STUDY TIME

            actions.append(
                button(
                    'AI Suggest Study Time',
                    async () => {
                        try {
                            notice(
                                'Finding study times...'
                            );

                            const result = await api(
                                '/api/suggest/' +
                                encodeURIComponent(a.id),
                                'POST'
                            );

                            await reload();

                            notice(
                                `${(result.suggestions || []).length} ` +
                                `study sessions proposed. ` +
                                `${result.hours_unscheduled} ` +
                                `hours still unscheduled.`
                            );

                        } catch (error) {
                            alert(error.message);
                        }
                    }
                )
            );

            // EDIT ESTIMATES

            actions.append(
                button('Edit Estimates', async () => {
                    const difficulty = prompt(
                        'Difficulty: Easy, Medium, or Hard',
                        a.difficulty || 'Medium'
                    );

                    if (difficulty === null) return;

                    const hours = prompt(
                        'Estimated hours',
                        a.estimated_hours || 2
                    );

                    if (hours === null) return;

                    try {
                        await api(
                            '/api/assignments/' +
                            encodeURIComponent(a.id),
                            'PATCH',
                            {
                                difficulty,
                                estimated_hours: Number(hours)
                            }
                        );

                        await reload();

                    } catch (error) {
                        alert(error.message);
                    }
                })
            );

            // DELETE ASSIGNMENT

            actions.append(
                button(
                    'Delete',
                    async () => {
                        if (
                            !confirm(
                                'Delete this assignment?'
                            )
                        ) {
                            return;
                        }

                        try {
                            await api(
                                '/api/assignments/' +
                                encodeURIComponent(a.id),
                                'DELETE'
                            );

                            await reload();

                        } catch (error) {
                            alert(error.message);
                        }
                    },
                    'danger'
                )
            );

            fragment.append(element);
        }

        list.replaceChildren(fragment);

        if (!filtered.length) {
            list.textContent = assignments.length
                ? 'No assignments match your filters.'
                : 'No assignments yet.';
        }

        assignmentUI.count.textContent =
            `Showing ${visible.length} of ` +
            `${filtered.length} matching assignments ` +
            `(${assignments.length} total).`;

        assignmentUI.more.hidden =
            visible.length >= filtered.length;
    }

    // RENDER COMMITMENTS

    function renderCommitments() {
        const list = $('commitmentList');

        // Do not build cards while the dropdown is closed.
        if (!isExpanded(list)) {
            list.replaceChildren();
            commitmentUI.more.hidden = true;
            return;
        }

        const query = commitmentUI.search.value
            .trim()
            .toLowerCase();

        const filtered = commitments.filter(c =>
            !query ||
            (c.title || '')
                .toLowerCase()
                .includes(query) ||
            (c.type || '')
                .toLowerCase()
                .includes(query) ||
            (c.date || '').includes(query)
        );

        filtered.sort((a, b) =>
            (a.date || '').localeCompare(
                b.date || ''
            )
        );

        const visible = filtered.slice(
            0,
            commitmentLimit
        );

        const fragment =
            document.createDocumentFragment();

        for (const c of visible) {
            const { element, actions } = createItem(
                c.title,
                `${c.type || 'Personal'} · ` +
                `${c.date} · ` +
                `${c.start_time}–${c.end_time}` +
                (c.repeat_weekly ? ' · Weekly' : '')
            );

            const select =
                document.createElement('select');

            select.setAttribute(
                'aria-label',
                'Commitment classification'
            );

            for (
                const value of [
                    'Fixed',
                    'Flexible',
                    'Free'
                ]
            ) {
                const option =
                    document.createElement('option');

                option.value = value;
                option.textContent = value;

                select.append(option);
            }

            select.value =
                c.flexibility || 'Fixed';

            select.addEventListener(
                'change',
                async () => {
                    try {
                        await api(
                            '/api/commitments/' +
                            encodeURIComponent(c.id),
                            'PATCH',
                            {
                                flexibility: select.value
                            }
                        );

                        await reload();

                    } catch (error) {
                        alert(error.message);
                    }
                }
            );

            actions.append(select);

            actions.append(
                button(
                    'Delete',
                    async () => {
                        if (
                            !confirm(
                                'Delete this commitment?'
                            )
                        ) {
                            return;
                        }

                        try {
                            await api(
                                '/api/commitments/' +
                                encodeURIComponent(c.id),
                                'DELETE'
                            );

                            await reload();

                        } catch (error) {
                            alert(error.message);
                        }
                    },
                    'danger'
                )
            );

            fragment.append(element);
        }

        list.replaceChildren(fragment);

        if (!filtered.length) {
            list.textContent = commitments.length
                ? 'No commitments match your search.'
                : 'No commitments yet.';
        }

        commitmentUI.count.textContent =
            `Showing ${visible.length} of ` +
            `${filtered.length} matching commitments ` +
            `(${commitments.length} total).`;

        commitmentUI.more.hidden =
            visible.length >= filtered.length;
    }

    // RENDER STUDY SESSIONS

    function renderSessions() {
        const list = $('sessionList');

        if (!isExpanded(list)) {
            list.replaceChildren();
            sessionUI.more.hidden = true;
            return;
        }

        const query = sessionUI.search.value
            .trim()
            .toLowerCase();

        const pending = sessions.filter(s =>
            s.status === 'pending' &&
            (
                !query ||
                (s.title || '')
                    .toLowerCase()
                    .includes(query)
            )
        );

        pending.sort((a, b) =>
            (a.starts || '').localeCompare(
                b.starts || ''
            )
        );

        const visible = pending.slice(
            0,
            sessionLimit
        );

        const fragment =
            document.createDocumentFragment();

        for (const s of visible) {
            const { element, actions } = createItem(
                s.title,
                `${s.starts.replace('T', ' ')} ` +
                `to ${s.ends.replace('T', ' ')}`
            );

            // APPROVE SESSION

            actions.append(
                button('Approve', async () => {
                    try {
                        const result = await api(
                            '/api/sessions/' + s.id,
                            'POST'
                        );

                        await reload();

                        notice(
                            'Approved. ' + result.google
                        );

                    } catch (error) {
                        alert(error.message);
                    }
                })
            );

            // REJECT SESSION

            actions.append(
                button(
                    'Reject',
                    async () => {
                        try {
                            await api(
                                '/api/sessions/' + s.id,
                                'DELETE'
                            );

                            await reload();

                        } catch (error) {
                            alert(error.message);
                        }
                    },
                    'danger'
                )
            );

            fragment.append(element);
        }

        list.replaceChildren(fragment);

        if (!pending.length) {
            list.textContent =
                'No pending sessions found.';
        }

        sessionUI.count.textContent =
            `Showing ${visible.length} of ` +
            `${pending.length} pending sessions.`;

        sessionUI.more.hidden =
            visible.length >= pending.length;
    }

    // BUILD HIDDEN LISTS ONLY WHEN OPENED

    for (
        const id of [
            'commitmentList',
            'sessionList'
        ]
    ) {
        const details = $(id).closest('details');

        if (details) {
            details.addEventListener(
                'toggle',
                () => {
                    if (id === 'commitmentList') {
                        renderCommitments();
                    } else {
                        renderSessions();
                    }
                }
            );
        }
    }

    // RELOAD DASHBOARD DATA

    async function reload() {
        const [
            newAssignments,
            newCommitments,
            newSessions
        ] = await Promise.all([
            api('/api/assignments'),
            api('/api/commitments'),
            api('/api/sessions')
        ]);

        assignments = newAssignments;
        commitments = newCommitments;
        sessions = newSessions;

        renderCalendar();
        renderAssignments();
        renderCommitments();
        renderSessions();
    }

    // ADD ASSIGNMENT

    $('assignmentForm').addEventListener(
        'submit',
        async event => {
            event.preventDefault();

            try {
                await api(
                    '/api/assignments',
                    'POST',
                    {
                        title: $('assignmentName').value,
                        course: $('courseName').value,
                        due_date: $('dueDate').value,
                        difficulty: $('difficulty').value,
                        estimated_hours:
                            $('estimatedHours').value || null
                    }
                );

                event.target.reset();

                await reload();

                notice(
                    'Assignment saved to SQLite.'
                );

            } catch (error) {
                alert(error.message);
            }
        }
    );

    // ADD COMMITMENT

    $('availabilityForm').addEventListener(
        'submit',
        async event => {
            event.preventDefault();

            try {
                await api(
                    '/api/commitments',
                    'POST',
                    {
                        title: $('commitmentName').value,
                        type: $('commitmentType').value,
                        date: $('commitmentDate').value,
                        start_time: $('startTime').value,
                        end_time: $('endTime').value,
                        flexibility: $('flexibility').value,
                        repeat_weekly: $('repeatWeekly').checked
                    }
                );

                event.target.reset();

                await reload();

                notice('Commitment saved.');

            } catch (error) {
                alert(error.message);
            }
        }
    );

    // CHECK AVAILABILITY

    $('checkAvailabilityForm').addEventListener(
        'submit',
        event => {
            event.preventDefault();

            const date = $('checkDate').value;
            const start = $('checkStart').value;
            const end = $('checkEnd').value;

            const result = $('availabilityResult');

            if (end <= start) {
                result.textContent =
                    'Invalid time range';
                return;
            }

            const weekday = new Date(
                date + 'T12:00:00'
            ).getDay();

            const clashes = commitments.filter(c =>
                c.flexibility !== 'Free' &&
                (
                    (
                        c.repeat_weekly &&
                        date >= c.date &&
                        new Date(
                            c.date + 'T12:00:00'
                        ).getDay() === weekday
                    ) ||
                    (
                        !c.repeat_weekly &&
                        c.date === date
                    )
                ) &&
                start < c.end_time &&
                end > c.start_time
            );

            clashes.push(
                ...sessions.filter(s =>
                    s.status !== 'rejected' &&
                    (date + 'T' + start) < s.ends &&
                    (date + 'T' + end) > s.starts
                )
            );

            result.textContent = clashes.length
                ? 'Busy: ' +
                  clashes.map(c => c.title).join(', ')
                : 'Available for studying!';

            result.style.color = clashes.length
                ? '#bf3242'
                : '#13774a';
        }
    );

    // AI CHAT

    function appendChat(kind, text) {
        const element =
            document.createElement('div');

        element.className =
            'chat-line ' + kind;

        element.textContent =
            (
                kind === 'user'
                    ? 'You: '
                    : 'StudyFlow: '
            ) + text;

        $('chatLog').append(element);

        $('chatLog').scrollTop =
            $('chatLog').scrollHeight;
    }

    $('chatForm').addEventListener(
        'submit',
        async event => {
            event.preventDefault();

            const message = $('chatMessage')
                .value
                .trim();

            if (!message) return;

            appendChat('user', message);

            $('chatMessage').value = '';

            try {
                const result = await api(
                    '/api/chat',
                    'POST',
                    { message }
                );

                appendChat('ai', result.reply);

                await reload();

            } catch (error) {
                appendChat(
                    'ai',
                    'Error: ' + error.message
                );
            }
        }
    );

    // CANVAS SYNC

    $('canvasSync').addEventListener(
        'click',
        async () => {
            try {
                notice(
                    'Importing Canvas assignments...'
                );

                const result = await api(
                    '/api/canvas/sync',
                    'POST'
                );

                await reload();

                notice(
                    'Canvas assignments processed: ' +
                    result.imported_or_seen
                );

            } catch (error) {
                alert(error.message);

                notice(
                    'Canvas import failed.'
                );
            }
        }
    );

    // GOOGLE CALENDAR SYNC

    $('googleSync').addEventListener(
        'click',
        async () => {
            try {
                notice(
                    'Synchronizing Google Calendar...'
                );

                const result = await api(
                    '/api/google/sync',
                    'POST'
                );

                await reload();

                notice(
                    'Google events synced: ' +
                    result.events_synced
                );

            } catch (error) {
                alert(error.message);

                notice(
                    'Google Calendar synchronization failed.'
                );
            }
        }
    );

    // INITIAL PAGE LOAD

    reload().catch(error => {
        notice(
            'Failed to load data: ' +
            error.message
        );
    });
});
