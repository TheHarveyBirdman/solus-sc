#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#  This file is part of solus-sc
#
#  Copyright © 2013-2018 Ikey Doherty <ikey@solus-project.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#

from gi.repository import AppStreamGlib as As
from gi.repository import Gio, GLib, GdkPixbuf, Gtk
from .media_fetcher import ScMediaFetcher


class Screenshot:
    """ Wrap AppStream screenshots into something usable. """

    main_uri = None
    thumb_uri = None
    default = None

    def __init__(self, asImg, scale):
        large = None
        normal = None
        thumbnail = None

        if asImg.get_kind() == As.ScreenshotKind.DEFAULT:
            self.default = True
        else:
            self.default = False

        # Loop em all with scale factor
        for image in asImg.get_images():
            if image.get_width() == As.IMAGE_LARGE_WIDTH * scale:
                large = image
            elif image.get_width() == As.IMAGE_NORMAL_WIDTH * scale:
                normal = image
            elif image.get_width() == As.IMAGE_THUMBNAIL_WIDTH * scale:
                thumbnail = image
            if large and normal and thumbnail:
                break
        # Couldn't find with scale factor so try with normal sizes
        if scale != 1:
            if not thumbnail or not normal:
                for image in asImg.get_images():
                    if image.get_width() == As.IMAGE_LARGE_WIDTH:
                        large = image
                    elif image.get_width() == As.IMAGE_NORMAL_WIDTH:
                        normal = image
                    elif image.get_width() == As.IMAGE_THUMBNAIL_WIDTH:
                        thumbnail = image
                    if large and normal and thumbnail:
                        break

        if large is None:
            large = normal

        if not normal or not thumbnail:
            raise RuntimeError("Invalid screenshot")

        self.main_uri = large.get_url()
        self.thumb_uri = thumbnail.get_url()


class AppSystem:
    """ Mux calls into AppStream where appropriate.

        This class enables failsafe queries for descriptions/summaries
        by hooking into AppSystem, and falling back to the native fields
        in the .eopkg's

        TODO: Locale integration
    """

    store = None
    default_pixbuf = None
    security_pixbuf = None
    mandatory_pixbuf = None
    other_pixbuf = None
    addon_pixbuf = None
    fetcher = None

    def __init__(self):
        self.fetcher = ScMediaFetcher()
        self.store = As.Store()
        self.store.load(As.StoreLoadFlags.APP_INFO_SYSTEM)

        itheme = Gtk.IconTheme.get_default()
        try:
            self.default_pixbuf = self.scaled_icon(itheme.load_icon(
                "package-x-generic",
                64,
                Gtk.IconLookupFlags.GENERIC_FALLBACK))
            self.security_pixbuf = self.scaled_icon(itheme.load_icon(
                "network-vpn",
                64,
                Gtk.IconLookupFlags.GENERIC_FALLBACK))
            self.mandatory_pixbuf = self.scaled_icon(itheme.load_icon(
                "computer",
                64,
                Gtk.IconLookupFlags.GENERIC_FALLBACK))
            self.other_pixbuf = self.scaled_icon(itheme.load_icon(
                "folder-download",
                64,
                Gtk.IconLookupFlags.GENERIC_FALLBACK))
            self.addon_pixbuf = self.scaled_icon(itheme.load_icon(
                "application-x-addon",
                64,
                Gtk.IconLookupFlags.GENERIC_FALLBACK))
        except Exception as e:
            print(e)

    def scaled_icon(self, pbuf):
        if pbuf.get_height() != 64:
            pbuf = pbuf.scale_simple(
                64, 64, GdkPixbuf.InterpType.BILINEAR)
        return pbuf

    def sanitize(self, text):
        return text.replace("&quot;", "\"")

    def get_summary(self, package):
        """ Return a usable summary for a package """
        app = self.store.get_app_by_pkgname(package.name)
        ret = None
        if not app:
            ret = GLib.markup_escape_text(str(package.summary))
        else:
            ret = app.get_comment("C")
        return self.sanitize(ret)

    def get_search_summary(self, package):
        """ Return a usable search summary for a package """
        app = self.store.get_app_by_pkgname(package.name)
        ret = None
        if not app:
            summary = str(package.summary)
            summary = summary.replace(" & ", " &amp; ")
            ret = GLib.markup_escape_text(summary)
        else:
            ret = app.get_comment("C")
        return self.sanitize(ret)

    def get_description(self, package):
        """ Return a usable description for a package """
        app = self.store.get_app_by_pkgname(package.name)
        description = str(package.description)
        if not app:
            return self.sanitize(
                GLib.markup_escape_text(description))
        c = app.get_description("C")
        if not c:
            return self.sanitize(
                GLib.markup_escape_text(description))
        return c

    def get_name(self, package):
        app = self.store.get_app_by_pkgname(package.name)
        if not app:
            return GLib.markup_escape_text(str(package.name))
        return GLib.markup_escape_text(self.sanitize(app.get_name("C")))

    def get_icon(self, package):
        """ Fallback method """
        if package.icon:
            return package.icon
        return "package-x-generic"

    def get_pixbuf(self, package):
        """ Get the AppStream GdkPixbuf for a package """
        app = self.store.get_app_by_pkgname(package.name)
        if not app:
            return None
        # TODO: Incorporate HIDPI!
        icon = app.get_icon_for_size(64, 64)
        if not icon:
            return self.default_pixbuf_lookup(app)
        kind = icon.get_kind()
        if kind == As.IconKind.UNKNOWN or kind == As.IconKind.REMOTE:
            return None
        if kind == As.IconKind.STOCK:
            # Load up a gthemedicon version
            im = Gio.ThemedIcon.new(icon.get_name())
            return im
        if not icon.load(As.IconLoadFlags.SEARCH_SIZE):
            return None
        return icon.get_pixbuf()

    def default_pixbuf_lookup(self, app):
        """ Use our built in preloaded pixbufs """
        if app is None:
            return self.default_pixbuf
        kind = app.get_kind()
        if kind == As.AppKind.ADDON:
            return self.addon_pixbuf
        return self.default_pixbuf

    def get_pixbuf_only(self, package):
        """ Only get a pixbuf - no fallbacks  """
        app = self.store.get_app_by_pkgname(package.name)
        if not app:
            return self.default_pixbuf_lookup(app)
        # TODO: Incorporate HIDPI!
        icon = app.get_icon_for_size(64, 64)
        if not icon:
            return self.default_pixbuf_lookup(app)
        kind = icon.get_kind()
        if kind == As.IconKind.UNKNOWN or kind == As.IconKind.REMOTE:
            return None
        if kind == As.IconKind.STOCK:
            # Load up a gthemedicon version
            try:
                itheme = Gtk.IconTheme.get_default()
                pbuf = itheme.load_icon(
                    icon.get_name(),
                    64,
                    Gtk.IconLookupFlags.GENERIC_FALLBACK)
                if pbuf.get_height() != 64:
                    pbuf = pbuf.scale_simple(
                        64, 64, GdkPixbuf.InterpType.BILINEAR)
                return pbuf
            except Exception as e:
                print(e)
            return self.default_pixbuf
        if not icon.load(As.IconLoadFlags.SEARCH_SIZE):
            return self.default_pixbuf
        pbuf = icon.get_pixbuf()
        if pbuf.get_height() != 64:
            pbuf = pbuf.scale_simple(
                64, 64, GdkPixbuf.InterpType.BILINEAR)
        return pbuf

    def _get_appstream_url(self, package, ptype):
        """ Get an appstream link for the given package """
        app = self.store.get_app_by_pkgname(package.name)
        if not app:
            return None
        url = app.get_url_item(ptype)
        return url

    def get_website(self, package):
        """ Get the website for a given package """
        home = self._get_appstream_url(package, As.UrlKind.HOMEPAGE)
        if home:
            return home
        if package.source.homepage:
            return str(package.source.homepage)
        return None

    def get_donation_site(self, package):
        """ Get a donation link for the given package """
        return self._get_appstream_url(package, As.UrlKind.DONATION)

    def get_bug_site(self, package):
        """ Get a bug link for the given package """
        return self._get_appstream_url(package, As.UrlKind.BUGTRACKER)

    def get_developers(self, package):
        """ Get the developer names for the given package """
        app = self.store.get_app_by_pkgname(package.name)
        if not app:
            return None
        return app.get_developer_name("C")

    def get_screenshots(self, package):
        """ Return wrapped Screenshot objects for the package """
        app = self.store.get_app_by_pkgname(package.name)
        if not app:
            return None
        screens = app.get_screenshots()
        if not screens:
            return None
        ret = []
        for screen in screens:
            try:
                # TODO: Pass scale factor
                img = Screenshot(screen, 1)
                ret.append(img)
            except Exception as e:
                print("Unable to load screen: {}".format(e))
        return ret
