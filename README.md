# Sybill coding assignment

## Running the application

Ensure you have `docker` and `docker-compose` installed, and run

```
docker-compose up
```

The REST API will be accessible at `localhost:8000`.

API documentation will be accessible at `localhost:8000/docs` and `locahost:8000/redoc`. API documentation can also be found as JSON at `openapi.json`.

An Insomnia collection for easier testing is provided in this repository, at `insomnia_request_collection.json`.

## Design choices

### Authentication and authorization

Users must provide a password upon registration (`POST /users`), which is stored hashed in the user document. Authentication follows simple OAuth2 standard, using a `POST /token` endpoint to verify username and password, and providing a JWT token for authentication of further requests.

Authorization is performed via OAuth2 scopes, where scopes are created for a user during registration. As a proof of concept, users can provide a boolean parameter `admin` during registration, which if true will create administrator scopes as well as shopper scopes.

For a production deployment, this should be replaced with a more secure management of administrator privileges.

### Core functionality not implemented

The endpoint responsible for performing a full update of a user was not implemented. Due to how the `username` field is used as a unique key for users, it was considered that allowing for a full user update might create inconsistencies in some edge cases. The endpoint for user partial updates allows for the update of all user fields except for `username`.

### Sorting and filtering limitations

Sorting was implemented as a single-field operation (the API doesn't support sorting for more than one field). And filtering is only supported for the `price` field of products.

### Cart API permissions

While `user` and `product` routes have some endpoints requiring `admin` permissions, and others only allowing for a user to modify its own data, all `cart` routes only allow for a user to modify carts associated with them.

## Production deployment

Before deployment to production, a more secure solution must be implemented to deal with administrator privileges. Ideally, the code should also be unit tested.

The current API code should be otherwise production ready. Deploying this service to a K8s cluster, with a ReplicaSet configured, should provide good reliability. The MongoDB deployment should be scaled accordingly, as well.