# Build image for `fsd`. Only needed if you want to unpack a disc on the
# server itself — to serve a site you built elsewhere, the caddy service in
# compose.yml is enough and this never gets built.
#
# No Ford content is baked in and none ever should be: the disc and the output
# are bind mounts. An image with the content in it would be a copyrighted
# 600 MB artefact one `docker push` away from being published.
FROM python:3.13-alpine

WORKDIR /app
COPY fsd/ /app/fsd/
COPY viewer/ /app/viewer/

# fsd is stdlib-only, so there is nothing to install.
ENTRYPOINT ["python3", "-m", "fsd"]
CMD ["--help"]
