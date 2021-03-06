;
PlaylistUi = function () {

    var self = this;

    this.interval = false;
    this.interval_loops = 0;
    this.interval_duration = 120000;
    this.api_url = false;
    this.api_url_simple = false; // used for listings as much faster..

    this.inline_dom_id = 'inline_playlist_holder';
    this.inline_dom_element;

    this.current_playlist_id;

    this.current_data;
    this.current_items = new Array;

    this.init = function () {

        console.log('PlaylistUi: init');
        console.log(self.api_url);

        this.inline_dom_element = $('#' + this.inline_dom_id);

        self.iface();
        self.bindings();
        self.load();

    };

    this.iface = function () {
        // this.floating_inline('lookup_providers', 120)
    };

    this.bindings = function () {

        var container = $('#inline_playlist_container');

        // states - open / close
        // main box
        $('.ui-persistent > .header', container).live('click', function (e) {
            e.preventDefault();
            var parent = $(this).parents('.ui-persistent');
            if (!parent.hasClass('expanded')) {
                parent.data('uistate', 'expanded');
            } else {
                parent.data('uistate', 'hidden');
            }
        });

        // settings panel / create
        $('.ui-persistent > .form form.create', container).live('submit', function (e) {
            e.preventDefault();
            var name = $('input.name', $(this)).val();
            self.create_playlist(name);
        });

        // actions
        $('.playlist_holder > .header a', container).live('click', function (e) {
            e.preventDefault();

            var id = $(this).parents('.playlist_holder').data('object_id');
            var action = $(this).data('action');


            //if (action == 'delete') {
            //
            //    var options = {
            //        title: 'Confirm',
            //        body: '<p>' + 'Are you sure?' + '</p>',
            //        buttons: [
            //            {
            //                label: 'Delete',
            //                hide: true,
            //                callback: function(e) {
            //                    self.delete_playlist(id);
            //                    conatiner.fadeOut(200)
            //                }
            //            }
            //        ]
            //    };
            //
            //    ui.dialog.show(options);
            //
            //}

            if (action == 'delete' && confirm('Sure?')) {
                self.delete_playlist(id);
                conatiner.fadeOut(200)
            }

        });


        // Playlist as a whole, edit name
        $('div.playlist_holder .header .action.edit').live('click', function () {
            var edit = $('div.edit', $(this).parent().parent().parent());
            if (edit.css("display") == "none") {
                edit.show();
            } else {
                edit.hide();
            }
            return false;
        });

        // Action on name change & Enter
        $('div.playlist_holder .panel .edit input').live('keypress', function (e) {

            if (e.keyCode == 13 || e.keyCode == 9) {
                e.preventDefault();
                var id = $(this).attr('id').split("_").pop();
                var name = $(this).val();
                var data = {
                    name: name
                };

                $.ajax({
                    url: self.api_url + id + '/',
                    type: 'PUT',
                    data: JSON.stringify(data),
                    dataType: "json",
                    contentType: "application/json",
                    processData: false,
                    success: function (data) {
                        self.run_interval();
                    },
                    async: true
                });
            }
        });

        // list items
        $('.action.download > a', self.inline_dom_element).live('click', function (e) {
            e.preventDefault();
        });

        // list-inner items
        $('.list.item a', self.inline_dom_element).live('click', function (e) {

            e.preventDefault();
            var container = $(this).parents('.list.item');
            var action = $(this).data('action');
            var resource_uri = container.data('resource_uri');

            if (action == 'delete') {
                container.remove()
                $.ajax({
                    url: resource_uri,
                    type: 'DELETE',
                    dataType: "json",
                    contentType: "application/json",
                    processData: false,
                    success: function (data) {
                        container.hide(1000)
                    },
                    async: true
                });
            }

            if (action == 'play') {

            }

        });

        // selector
        $('#playlists_inline_selector').live('change', function (e) {
            e.preventDefault();

            var resource_uri = $(this).val();
            $('.playlist_holder', self.inline_dom_element).hide();

            $.ajax({
                url: resource_uri + 'set-current/',
                type: 'GET',
                dataType: "json",
                contentType: "application/json",
                processData: false,
                success: function (data) {
                    self.load();
                },
                async: true
            });

        });


    };

    // interval
    this.set_interval = function (method, duration) {
        self.interval = setInterval(method, duration);
    };
    this.clear_interval = function (method) {
        self.interval = clearInterval(method);
    };

    this.run_interval = function () {
        self.interval_loops += 1;
        self.update_playlists();
    };

    this.create_playlist = function (name) {

        var data = {
            'name': name,
            'type': 'basket'
        };

        $.ajax({
            url: self.api_url,
            type: 'POST',
            data: JSON.stringify(data),
            dataType: "json",
            contentType: "application/json",
            processData: false,
            success: function (data) {
                $('> div', self.inline_dom_element).remove();
                // self.run_interval();
                self.load();
            },
            async: true
        });

    };


    this.delete_playlist = function (id) {

        $.ajax({
            url: self.api_url + id + '/',
            type: 'DELETE',
            dataType: "json",
            contentType: "application/json",
            processData: false,
            success: function (data) {
                $('#playlist_holder_' + id).fadeOut(160, function () {
                    $(this).remove();
                });

                self.load();
            },
            async: true
        });
    };

    this.update_playlists = function () {

    };

    /* refactored */
    this.update_playlists_callback = function (data) {
        self.update_playlist_display(data);
        self.update_playlist_selector(data);
        this.current_data = data;
    };


    this.load = function () {

        // get & display data
        $.getJSON(self.api_url + '?is_current=1', function (data) {

            console.log(self.api_url + '?is_current=1')

            self.update_playlist_display(data);
            this.current_data = data;

            pushy.subscribe(self.api_url + data.objects[0].id + '/', function () {
                self.load();
            });


            // maybe not the best way. think about alternatives...
            try {
                alibrary.playlist_editor.rebind();
            } catch (e) {
                console.log('error', e);
            }

        });


        setTimeout(function () {
            $.getJSON(self.api_url_simple + '?type__in=playlist,basket', function (data) {
                self.update_playlist_selector(data);
            });
        }, 100)


    };

    this.update_playlist_display = function (data) {


        for (var i in data.objects) {

            var item = data.objects[i];
            var target_element = $('#playlist_holder_' + item.id);


            // filter out current playlist
            if (item.is_current) {

                // var html = ich.tpl_playlists_inline({object: item});
                var html = nj.render('alibrary/nj/playlist/listing_inline.html', {
                    object: item
                });
                // console.log('item:', item)

                self.inline_dom_element.html(html);

                self.current_items[item.id] = item;

                try {
                    pushy.subscribe(item.resource_uri, self.update_playlists);
                } catch (e) {
                    //console.log('error subscribe to pushy:', e);
                }

            } else {
                // remove item if not the current one
                target_element.remove();
            }
        }
    };

    this.update_playlist_selector = function (data) {

        if (data.objects.length > 1) {

            if (!Object.equals(this.current_data, data)) {
                console.log('data changed');

                var html = ich.tpl_playlists_inline_selector(data);
                $('.playlist-selector', self.inline_dom_element.parent()).html(html);

            } else {
                console.log('data unchanged');
            }

        } else {
            $('.playlist-selector', self.inline_dom_element.parent()).html('');
        }
    };


};


CollectorApp = (function () {

    var self = this;
    this.api_url;
    this.playlist_app;
    this.mode = 'main'; // or popup
    this.qs_limit = 50;

    this.active_playlist = false;

    this.use_effects = true;
    this.animation_target = ".playlist.basket";

    this.playlists_local = false;
    this.media_to_collect = false;

    this.popup_api = false;
    this.popup_container = false;

    this.init = function () {
        this.bindings();
    };


    this.bindings = function () {


        $('body').on('click', 'a[data-action=collect]', function (e) {

            e.preventDefault();
            e.stopPropagation();

            if (self.popup_api) {
                self.popup_api.destroy();
            }

            var container = $(this).parents('.item');
            var resource_uri = container.data('resource_uri');
            var media = [];

            self.media_to_collect = false;

            // type switch
            if (container.hasClass('media')) {

                var item_id = container.data('id');
                var item_uuid = container.data('uuid');
                media.push({id: item_id, uuid: item_uuid});

                self.media_to_collect = media;

            }

            // release -> we need to get it's media first
            if (container.hasClass('release')) {

                $.ajax({
                    url: resource_uri,
                    success: function (data) {
                        for (i in data.media) {
                            var item = data.media[i];
                            media.push({id: item.id, uuid: item.uuid});
                        }
                        self.media_to_collect = media;
                    },
                    // callbacks etc
                    async: false
                });
            }

            // playlistitem (exists in playlist editor only a.t.m.)
            if (container.hasClass('playlistitem')) {

                if(container.data('ct') != 'media') {
                    // only tracks a.k.a. media can be collected
                    return;
                }

                var item_id = container.data('ct_id');
                var item_uuid = container.data('ct_uuid');
                media.push({id: item_id, uuid: item_uuid});

                self.media_to_collect = media;
                
            }

            // playlist -> we need to get it's media first
            if (container.hasClass('playlist')) {

                $.ajax({
                    url: resource_uri + '?all=1',
                    success: function (data) {

                        for (i in data.items) {
                            var item = data.items[i].item;
                            if(item.content_type == 'media') {
                                media.push({id: item.content_object.id, uuid: item.content_object.uuid});
                            }
                        }

                        self.media_to_collect = media;
                    },
                    // callbacks etc
                    async: false
                });
            }

            // special situation - action invoked from sidebar
            if($(this).hasClass('selection-required')){
                // alert('sidebar')
                _media = [];
                $('.list_body .item.selection').each(function(i, el){
                    el = $(el);
                    var item_id = el.data('id');
                    var item_uuid = el.data('uuid');
                    _media.push({id: item_id, uuid: item_uuid});

                });

                self.media_to_collect = _media;

            }


            if(self.media_to_collect && self.media_to_collect.length){

                if(self.mode == 'main') {
                    self.dialogue(e)
                } else if(self.mode == 'popup') {
                    self.dialogue_popup(e)
                } else {
                    return;
                }

            }

        });


    };

    this.dialog_bindings = function (api) {

        var el = api.elements.tooltip;

        self.popup_api = api;
        self.popup_container = el;

        // remove handlers first
        el.off('click');

        // nano scroll
        // TODO: re-enable nano scroller. having issue a.t.m.
        //$('.listing.nano', el).nanoScroller({ flash: false, preventPageScrolling: true });

        // search / filter
        el.on('keyup', 'input.search', function (e) {

            var q = $(this).val();

            if(q.length < 2){
                $('.item', el).removeClass('hidden');
            } else {
                $('.item', el).addClass('hidden');
                $('.item', el).each(function(i, item){
                    var name = $(this).data('name').toLowerCase();
                    if (name.indexOf(q) != -1) {
                        $(this).removeClass('hidden');
                    }
                });
            }

        });
        $('input.search', el).focus();

        // item actions
        el.on('click', '.item.playlist', function (e) {

            // don't do if link clicked
            if(!$(e.target).is("a")) {

                var item = {
                    el: $(this),
                    uuid: $(this).data('uuid'),
                    id: $(this).data('id'),
                    resource_uri: $(this).data('resource_uri')
                };
                var media = self.media_to_collect;
                self.collect(item, media);
            }



        });

        // form actions
        el.on('click', 'a[data-action]', function (e) {
            var action = $(this).data('action');
            if (action == 'cancel') {
                api.hide();
            }
            if (action == 'save') {

                var input = $('input.name', $(this).parents('.form'));
                if (input.val().length < 1) {
                    return false;
                } else {
                    self.create_playlist(input.val());
                    input.val('');
                }
            }
            if (action == 'load-more') {
                alert('Not implemented yet - Sorry.')
            }
        });
        el.on('keydown', 'input.name', function (e) {

            if(e.keyCode == 13) {
                e.preventDefault();
                $(this).parent().find('a[data-action="save"]').click()
            }

        });
        el.on('keydown', function (e) {

            if(e.keyCode == 27) {
                e.preventDefault();
                api.hide();
            }

        });

        self.update_dialog_markers();

    };


    this.update_dialog_markers = function () {

        var el = self.popup_container;
        var local_uuids = [];
        $.each(self.media_to_collect, function (i, media) {
            //console.log(media)
            local_uuids.push(media.uuid);
        });

        $('.collected', el).html('');

        $.each(self.playlists_local.objects, function (i, item) {

            var container = $('.' + item.uuid, el);
            var matches = 0;

            // loop items and compare
            $.each(item.item_uuids, function (j, uuid) {

                if ($.inArray(uuid, local_uuids) > -1) {
                    matches++
                }

            });
            if (matches > 0) {
                var html = '<i class="icon icon-star"></i>';
                $('.collected', container).html(html);
                container.addClass('match');
            } else {
                container.removeClass('match');
            }

        });


    };

    this.create_playlist = function (name, type) {

        var data = {
            'name': name,
            'type': (type != undefined) ? type : 'basket'
        };

        $.ajax({
            url: self.api_url,
            type: 'POST',
            data: JSON.stringify(data),
            dataType: "json",
            contentType: "application/json",
            processData: false,
            success: function (data) {
                // self.load(true);
                var el = self.popup_container;
                var html = nj.render('alibrary/nj/playlist/select_popup_item.html', { item: data });

                $('.listing .content p.notice', el).fadeOut(500);

                //$('.listing .content', el).append(html);
                //$('.listing.nano', el).nanoScroller({ scroll: 'bottom' });

                $('.listing .content', el).prepend(html);
                $('.listing.nano', el).nanoScroller({ scroll: 'top' });

                // reset the playlist cache
                // self.playlists_local = false;

                // append to cache
                self.playlists_local.objects.push(data)

            },
            async: true
        });

        // console.log('data:', data);

        // self.run_interval();
    };


    /*
        generic "add to playlist" dialog
     */
    this.get_dialog_content = function (api) {

        if (self.playlists_local) {
            setTimeout(function () {
                self.dialog_bindings(api);
            }, 10);
            return self.render_dialog_content(self.playlists_local)
        } else {
            var uri = '/api/v1/library/simpleplaylist/';
            $.ajax({
                url: uri + '?limit=' + self.qs_limit + '&type__in=playlist,basket',
                success: function (data) {
                    self.playlists_local = data;
                    api.set({
                        'content.text': self.render_dialog_content(self.playlists_local)
                    });
                    self.dialog_bindings(api);
                },
                async: true
            });
        }
        return '<p>loading</p>';
    };

    this.render_dialog_content = function (data) {

        console.debug('pl data:', data)

        var html = nj.render('alibrary/nj/playlist/select_popup.html', {
            data: data
        });
        return html;
    };


    // dialogue version used for inline selection (main window)
    this.dialogue = function (e) {

        $('<div />').qtip({
            content: {
                text: function (e, api) {
                    return self.get_dialog_content(api);
                },
                title: false
            },
            position: {
                my: 'top right',
                at: 'bottom left',
                target: $(e.currentTarget),
                viewport: $(window),
                adjust: {
                    x: -2,
                    scroll: true,
                    resize: true,
                    method: 'flipinvert'
                }

            },
            show: {
                ready: true,
                modal: {
                    on: false,
                    blur: true,
                    escape: true
                }
            },
            hide: false,
            style: 'qtip-dark qtip-dialogue qtip-shadow qtip-rounded select-playlist',
            events: {
                render: function (e, api) {
                    // $('body *').click(api.hide);
                    // var tooltip = api.elements.tooltip;
                    var timeout = false;
                    $(api.elements.tooltip).on('mouseover', function () {
                        clearTimeout(timeout);
                    });
                    $(api.elements.tooltip).on('mouseleave', function () {
                        timeout = setTimeout(function () {
                            api.destroy();
                        }, 500);
                    });

                }
            }
        });
    };

    // dialogue version used for full-screen selection (popup window)
    this.dialogue_popup = function (e) {

        $('<div />').qtip({
            content: {
                text: function (e, api) {
                    return self.get_dialog_content(api);
                },
                title: false
            },
            position: {
                my: 'center',
                at: 'center',
                target: $(window)
            },
            show: {
                ready: true,
                modal: {
                    on: false,
                    blur: false
                }
            },
            hide: false,
            style: 'qtip-dark qtip-dialogue select-playlist-popup'

        });
    };


    this.collect = function (item, media) {


        item.el.addClass('loading');

        var ids = [];
        $.each(media, function (i, x) {
            ids.push(x.id);
        });

        var data = {
            ids: ids.join(','),
            ct: 'media'
        };

        jQuery.ajax({
            url: item.resource_uri.replace('simple', '') + 'collect/',
            type: 'POST',
            data: JSON.stringify(data),
            dataType: "json",
            contentType: "application/json",
            processData:  false,
            success: function (data) {
                var html = nj.render('alibrary/nj/playlist/select_popup_item.html', { item: data });
                item.el.replaceWith(html);

                var el = $('.' + data.uuid);
                el.removeClass('loading');


                // kind of hackish... loop lists, compare uuids and ev replace item
                var exists = false;
                $.each(self.playlists_local.objects, function (i, playlist) {
                    if(playlist.uuid == data.uuid) {

                        self.playlists_local.objects[i] = data;
                        exists = true;
                    }

                });

                // not found -> push to list
                if (! exists) {
                    self.playlists_local.objects.push(data)
                }

                self.dialog_bindings(self.popup_api);
            },
            async: true
        });

    };



});


// selector to set active playlist
// currently used in popup-player
PlaylistSelector = function () {

    var self = this;

    this.interval = false;
    this.interval_loops = 0;
    this.interval_duration = false;
    this.api_url_simple = false; // used for listings as much faster..

    this.dom_id;
    this.dom_element;

    this.current_data;

    this.init = function () {

        this.dom_element = $('#' + this.dom_id);

        self.iface();
        self.bindings();

        // set interval and run once
        if (self.interval_duration) {
            self.set_interval(self.run_interval, self.interval_duration);
        }
        self.run_interval();

    };

    this.iface = function () {

    };

    this.bindings = function () {
        // selector
        $('select', self.dom_element).live('change', function (e) {
            e.preventDefault();
            var resource_uri = $(this).val();

            $.ajax({
                url: resource_uri + 'set-current/',
                type: 'GET',
                dataType: "json",
                contentType: "application/json",
                processData: false,
                success: function (data) {
                    self.run_interval();
                },
                async: true
            });


        });
    };

    // interval
    this.set_interval = function (method, duration) {
        self.interval = setInterval(method, duration);
    };
    this.clear_interval = function (method) {
        self.interval = clearInterval(method);
    };

    this.run_interval = function () {
        self.interval_loops += 1;
        self.update();

    };


    this.update = function () {

        var selector = $('select', self.dom_element);

        $.getJSON(self.api_url_simple + '?type__in=playlist,basket', function (data) {

            var html = '';
            for (i in data.objects) {
                var item = data.objects[i];
                //console.log('item:', item);

                html += '<option';
                if (item.is_current) {
                    html += ' selected="selected" ';
                }
                html += ' value="' + item.resource_uri + '" ';
                html += ' >'
                html += item.name;
                html += ' [' + item.item_count + ']';
                html += '</option>';
            }
            ;
            selector.html(html);

        });
    };

};


Object.equals = function (x, y) {
    if (x === y) return true;
    // if both x and y are null or undefined and exactly the same

    if (!( x instanceof Object ) || !( y instanceof Object )) return false;
    // if they are not strictly equal, they both need to be Objects

    if (x.constructor !== y.constructor) return false;
    // they must have the exact same prototype chain, the closest we can do is
    // test there constructor.

    for (var p in x) {
        if (!x.hasOwnProperty(p)) continue;
        // other properties were tested using x.constructor === y.constructor

        if (!y.hasOwnProperty(p)) return false;
        // allows to compare x[ p ] and y[ p ] when set to undefined

        if (x[ p ] === y[ p ]) continue;
        // if they have the same strict value or identity then they are equal

        if (typeof( x[ p ] ) !== "object") return false;
        // Numbers, Strings, Functions, Booleans must be strictly equal

        if (!Object.equals(x[ p ], y[ p ])) return false;
        // Objects and Arrays must be tested recursively
    }

    for (p in y) {
        if (y.hasOwnProperty(p) && !x.hasOwnProperty(p)) return false;
        // allows x[ p ] to be set to undefined
    }
    return true;
};