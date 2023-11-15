%global gem_name bundler

# Enable test when building on local.
%bcond_with tests

# Ideally it should be checked against FileUtils::VERSION.
# https://github.com/ruby/fileutils/pull/12
%global fileutils_version 0.7.2
%global molinillo_version 0.6.4
%global net_http_persistent_version 2.9.4
%global thor_version 0.20.0

Name: rubygem-%{gem_name}
Version: 1.16.1
Release: 4%{?dist}
Summary: Library and utilities to manage a Ruby application's gem dependencies
Group: Development/Languages
License: MIT
URL: http://bundler.io
Source0: https://rubygems.org/gems/%{gem_name}-%{version}.gem
# git clone https://github.com/bundler/bundler.git && cd bundler
# git checkout v1.16.1 && tar czvf bundler-1.16.1-specs.tgz spec/
Source1: %{gem_name}-%{version}-specs.tgz
# Raise an error or print a warning in dependency confusion cases.
# https://github.com/rubygems/rubygems/pull/5029
Patch0: ruby-bundler-raise-error-in-dependency-confusion.patch
Patch1: ruby-bundler-raise-error-in-dependency-confusion-tests.patch
# ruby package has just soft dependency on rubygem(io-console), while
# Bundler always requires it.
Requires: rubygem(io-console)
BuildRequires: ruby(release)
BuildRequires: rubygems-devel
BuildRequires: ruby
%if %{with tests}
BuildRequires: ruby-devel
BuildRequires: rubygem(rspec) >= 3.0
BuildRequires: rubygem(rake)
BuildRequires: git
BuildRequires: %{_bindir}/ps
%endif
# https://github.com/bundler/bundler/issues/3647
Provides: bundled(rubygem-fileutils) = %{fileutils_version}
Provides: bundled(rubygem-molinillo) = %{molinillo_version}
Provides: bundled(rubygem-net-http-persisntent) = %{net_http_persistent_version}
Provides: bundled(rubygem-thor) = %{thor_version}
BuildArch: noarch

%description
Bundler manages an application's dependencies through its entire life, across
many machines, systematically and repeatably.


%package doc
Summary: Documentation for %{name}
Group: Documentation
Requires: %{name} = %{version}-%{release}
BuildArch: noarch

%description doc
Documentation for %{name}.

%prep
%setup -q -c -T
%gem_install -n %{SOURCE0}

pushd .%{gem_instdir}
%patch0 -p1
popd

%build

%install
mkdir -p %{buildroot}%{gem_dir}
cp -a .%{gem_dir}/* \
        %{buildroot}%{gem_dir}/


mkdir -p %{buildroot}%{_bindir}
cp -a .%{_bindir}/* \
        %{buildroot}%{_bindir}/

find %{buildroot}%{gem_instdir}/exe -type f | xargs chmod a+x

# Remove unnecessary executable bit.
# https://github.com/bundler/bundler/pull/6285
chmod a-x %{buildroot}%{gem_libdir}/bundler/templates/Executable

# Man pages are used by Bundler internally, do not remove them!
for n in 5 1; do
  mkdir -p %{buildroot}%{_mandir}/man${n}
  for file in %{buildroot}%{gem_instdir}/man/*.${n}; do
    base_name=$(basename "${file}")
    cp -a "${file}" "%{buildroot}%{_mandir}/man${n}/${base_name}"
  done
done

%check
pushd .%{gem_instdir}
# Check bundled libraries.
[ `ls lib/bundler/vendor | wc -l` == 4 ]

ruby -e '
  module Bundler; end
  require "./lib/bundler/vendor/fileutils/lib/fileutils.rb"'

[ `ruby -e '
  module Bundler; end
  require "./lib/bundler/vendor/molinillo/lib/molinillo/gem_metadata"
  puts Bundler::Molinillo::VERSION'` == '%{molinillo_version}' ]

[ `ruby -Ilib -e '
  module Bundler; module Persistent; module Net; module HTTP; end; end; end; end
  require "./lib/bundler/vendor/net-http-persistent/lib/net/http/persistent"
  puts Bundler::Persistent::Net::HTTP::Persistent::VERSION'` == '%{net_http_persistent_version}' ]

[ `ruby -e '
  module Bundler; end
  require "./lib/bundler/vendor/thor/lib/thor/version"
  puts Bundler::Thor::VERSION'` == '%{thor_version}' ]

# Test suite has to be disabled for official build, since it downloads various
# gems, which are not in Fedora or they have different version etc.
# Nevertheless, the test suite should run for local builds.
%if %{with tests}

tar xzvf %{SOURCE1}
cat %{PATCH1} | patch -p1

# Re-create bundler.gemspec used in spec/spec_helper.rb to avoid unnecessary
# git dependency.
gem spec %{SOURCE0} -l --ruby > %{gem_name}.gemspec

# Color tests do not work in mock building process (but this can be tested
# running from shell).
# https://github.com/rpm-software-management/mock/issues/136
sed -i '/^          context "with color" do$/,/^          end$/ s/^/#/' \
  spec/bundler/source_spec.rb

# This test fails due to rubypick.
sed -i '/^      it "like a normally executed executable" do$/,/^      end$/ s/^/#/' \
  spec/commands/exec_spec.rb

# RDoc is not default gem on Fedora.
sed -i '/^    context "given a default gem shippped in ruby" do$/,/^    end$/ s/^/#/' \
  spec/commands/info_spec.rb

# Avoid unexpected influence of Fedora specific configuration. This forces
# Ruby to load this empty operating_system.rb instead of operatin_system.rb
# shipped as part of RubyGems.
mkdir -p %{_builddir}/rubygems/rubygems/defaults/
touch %{_builddir}/rubygems/rubygems/defaults/operating_system.rb

# Suppress warnings by "git init" on Git >= 2.28.
# Running `git config --global init.defaultBranch <name>` is not enough.
# https://github.blog/2020-07-27-highlights-from-git-2-28/
for file in \
  lib/bundler/cli/gem.rb \
  spec/bundler/gem_helper_spec.rb \
  spec/commands/show_spec.rb \
  spec/support/builders.rb
do
  sed -E -i 's|(git init( --bare)?)|\1 2> /dev/null|' $file
done

# It is necessary to require spec_helper.rb explicitly.
# https://github.com/bundler/bundler/pull/5634
# To pass other tests, set BUNDLE_DISABLE_DEPENDENCY_CONFUSION_CHECK
RUBYOPT=-I%{_builddir}/rubygems GEM_PATH=/usr/share/gems \
BUNDLE_DISABLE_DEPENDENCY_CONFUSION_CHECK=1 \
rspec -rspec_helper spec -f d

%endif

popd

%files
%dir %{gem_instdir}
%{_bindir}/bundle
%{_bindir}/bundler
%exclude %{gem_instdir}/.*
%exclude %{gem_libdir}/bundler/ssl_certs/index.rubygems.org
%exclude %{gem_libdir}/bundler/ssl_certs/rubygems.global.ssl.fastly.net
%exclude %{gem_libdir}/bundler/ssl_certs/rubygems.org
%exclude %{gem_libdir}/bundler/ssl_certs/.document
%license %{gem_instdir}/LICENSE.md
%exclude %{gem_instdir}/bundler.gemspec
%{gem_instdir}/exe
%{gem_libdir}
%exclude %{gem_instdir}/man/*.ronn
%doc %{gem_instdir}/man
%exclude %{gem_cache}
%{gem_spec}
%doc %{_mandir}/man1/*
%doc %{_mandir}/man5/*

%files doc
%doc %{gem_docdir}
%doc %{gem_instdir}/CHANGELOG.md
%doc %{gem_instdir}/README.md

%changelog
* Mon Dec 13 2021 Jun Aruga <jaruga@redhat.com> - 1.16.1-4
- Fix Bundler dependency confusion.
  Resolves: CVE-2020-36327

* Fri Feb 09 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.16.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Thu Feb 01 2018 Vít Ondruch <vondruch@redhat.com> - 1.16.1-2
- Remove unnecessary executable bit.

* Tue Jan 02 2018 Jun Aruga <jaruga@redhat.com> - 1.16.1-1
- Update to Bundler 1.16.1.

* Mon Nov 06 2017 Jun Aruga <jaruga@redhat.com> - 1.16.0-1
- Update to Bundler 1.16.0.

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.13.7-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.13.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Mon Jan 02 2017 Vít Ondruch <vondruch@redhat.com> - 1.13.7-1
- Update to Bundler 1.13.7.

* Fri Dec 16 2016 Vít Ondruch <vondruch@redhat.com> - 1.13.6-1
- Update to Bundler 1.13.6.

* Wed Jul 27 2016 Vít Ondruch <vondruch@redhat.com> - 1.12.5-1
- Update to Bundler 1.12.5.

* Fri Apr 08 2016 Vít Ondruch <vondruch@redhat.com> - 1.10.6-3
- Explicitly set rubygem(io-console) dependency.

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.10.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Mon Oct 12 2015 Vít Ondruch <vondruch@redhat.com> - 1.10.6-1
- Update to Bundler 1.10.6.
- Keep vendored libraries.

* Thu Jun 18 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.7.8-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Thu Feb 05 2015 Vít Ondruch <vondruch@redhat.com> - 1.7.8-2
- Properly uninstall the vendor directory.

* Tue Dec 09 2014 Vít Ondruch <vondruch@redhat.com> - 1.7.8-1
- Update to Bundler 1.7.8.

* Thu Nov 20 2014 Josef Stribny <jstribny@redhat.com> - 1.7.6-2
- Keep ssl_certs/certificate_manager.rb file (used in tests)
- Correctly add load paths for gems during tests

* Wed Nov 12 2014 Josef Stribny <jstribny@redhat.com> - 1.7.6-1
- Update to 1.7.6

* Tue Nov 11 2014 Josef Stribny <jstribny@redhat.com> - 1.7.4-2
- Use symlinks for vendored libraries (rhbz#1163039)

* Mon Oct 27 2014 Vít Ondruch <vondruch@redhat.com> - 1.7.4-1
- Update to Bundler 1.7.4.
- Add thor and net-http-persistent dependencies into .gemspec.

* Mon Sep 22 2014 Josef Stribny <jstribny@redhat.com> - 1.7.3-1
- Update to 1.7.3

* Sun Jun 08 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.5.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Sun Jan 12 2014 Sam Kottler <skottler@fedoraproject.org> - 1.5.2-1
- Update to 1.5.2 (BZ #1047222)

* Sun Aug 04 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.3.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Tue Jun 11 2013 Vít Ondruch <vondruch@redhat.com> - 1.3.5-1
- Update to Bundler 1.3.5.

* Mon Mar 04 2013 Josef Stribny <jstribny@redhat.com> - 1.3.1-1
- Rebuild for https://fedoraproject.org/wiki/Features/Ruby_2.0.0
- Update to Bundler 1.3.1

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.2.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Fri Nov 02 2012 Bohuslav Kabrda <bkabrda@redhat.com> - 1.2.1-1
- Update to Bundler 1.2.1.
- Fix permissions on some executable files.

* Sat Jul 21 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.1.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Fri Jul 13 2012 Vít Ondruch <vondruch@redhat.com> - 1.1.4-1
- Update to Bundler 1.1.4.

* Wed Feb 01 2012 Vít Ondruch <vondruch@redhat.com> - 1.0.21-1
- Rebuilt for Ruby 1.9.3.
- Update to Bundler 1.0.21.

* Sat Jan 14 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.15-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Thu Jul 07 2011 Vít Ondruch <vondruch@redhat.com> - 1.0.15-1
- Updated to Bundler 1.0.15

* Wed Feb 09 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.10-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Fri Feb 04 2011 Vít Ondruch <vondruch@redhat.com> - 1.0.10-1
- Upstream update

* Thu Jan 27 2011 Vít Ondruch <vondruch@redhat.com> - 1.0.9-2
- More concise summary
- Do not remove manpages, they are used internally
- Added buildroot cleanup in clean section

* Mon Jan 24 2011 Vít Ondruch <vondruch@redhat.com> - 1.0.9-1
- Bumped to Bundler 1.0.9
- Installed manual pages
- Removed obsolete buildroot cleanup

* Mon Nov 1 2010 Jozef Zigmund <jzigmund@redhat.com> - 1.0.3-2
- Add ruby(abi) dependency
- Add using macro %%{geminstdir} in files section
- Add subpackage doc for doc files
- Removed .gitignore file
- Removed rubygem-thor from vendor folder
- Add dependency rubygem(thor)

* Mon Oct 18 2010 Jozef Zigmund <jzigmund@redhat.com> - 1.0.3-1
- Initial package
